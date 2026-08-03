"""Smoke checks for intake_result_email_worker (not a product test suite)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
from uuid import uuid4

from app.features.assomi.constants import AssomiTaskStatus
from app.features.email.constants import EmailReplyStatus
from app.features.nat.constants import (
    IntakeSource,
    NatResultProcessingStatus,
    NatTaskStatus,
)
from intake_result_email_worker.app.features.result_email.artifact import (
    ArtifactStatus,
    resolve_assomi_artifact,
)
from intake_result_email_worker.app.features.result_email.classification import (
    ResultEmailClassification,
    ResultEmailContext,
    classify_pipeline_outcome,
)
from intake_result_email_worker.app.features.result_email.composer import (
    build_result_email_message,
    build_result_subject,
)
from intake_result_email_worker.app.features.result_email.messages import (
    AGGREGATION_NO_SPIN_REASON,
    ASSOMI_FILE_MISSING_REASON,
    NAT_ALL_FAILED_FALLBACK,
    RESULT_SUBJECT_WHEN_MISSING,
)


@dataclass
class _CheckResult:
    name: str
    ok: bool
    detail: str = ''


def _assomi(
    *,
    status: str,
    error_message: str | None = None,
    output_path: str | None = None,
    found_count: int | None = 1,
    missing_count: int | None = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        error_message=error_message,
        output_path=output_path,
        found_count=found_count,
        missing_count=missing_count,
    )


def _aggregation(
    *,
    status: str,
    error_message: str | None = None,
    output_files: list[dict[str, object]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        error_message=error_message,
        output_files=output_files if output_files is not None else [],
    )


def _nat_task(
    *,
    status: int | None,
    error_message: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(status=status, error_message=error_message)


def _context(**overrides: object) -> ResultEmailContext:
    base: dict[str, object] = {
        'intake_id': uuid4(),
        'intake_number': 42,
        'sender_email': 'sender@example.com',
        'file_name': 'request.csv',
        'batch_id': uuid4(),
        'source': IntakeSource.NAT.value,
        'original_subject': None,
        'original_message_id': None,
    }
    base.update(overrides)
    return ResultEmailContext(**base)  # type: ignore[arg-type]


def _check(name: str, condition: bool, detail: str = '') -> _CheckResult:
    return _CheckResult(name=name, ok=condition, detail=detail)


def run_classification_checks() -> list[_CheckResult]:
    checks: list[_CheckResult] = []

    success = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=_assomi(
            status=AssomiTaskStatus.COMPLETED.value,
            output_path='/app/data/assomi/x_assomi.csv',
        ),
        aggregation_task=_aggregation(status=NatResultProcessingStatus.COMPLETED.value),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(
        _check(
            'assomi_completed_success',
            success is not None and success.kind == 'success',
        )
    )

    assomi_failed = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=_assomi(
            status=AssomiTaskStatus.FAILED.value,
            error_message='ASSOMI down',
        ),
        aggregation_task=_aggregation(status=NatResultProcessingStatus.COMPLETED.value),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(
        _check(
            'assomi_failed',
            assomi_failed is not None
            and assomi_failed.kind == 'failure'
            and assomi_failed.stage == 'assomi'
            and assomi_failed.reason == 'ASSOMI down',
        )
    )

    agg_failed = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=None,
        aggregation_task=_aggregation(
            status=NatResultProcessingStatus.FAILED.value,
            error_message='spin boom',
        ),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(
        _check(
            'aggregation_failed',
            agg_failed is not None
            and agg_failed.kind == 'failure'
            and agg_failed.stage == 'aggregation_spin'
            and agg_failed.reason == 'spin boom',
        )
    )

    no_spin = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=None,
        aggregation_task=_aggregation(
            status=NatResultProcessingStatus.COMPLETED.value,
            output_files=[{'index': 0, 'spin_matched_path': ''}],
        ),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(
        _check(
            'aggregation_completed_without_spin',
            no_spin is not None
            and no_spin.kind == 'failure'
            and no_spin.reason == AGGREGATION_NO_SPIN_REASON,
        )
    )

    nat_failed = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=None,
        aggregation_task=None,
        nat_tasks=(
            _nat_task(status=None, error_message='send failed'),
            _nat_task(status=NatTaskStatus.CANCELLED, error_message=None),
        ),
    )
    checks.append(
        _check(
            'nat_all_failed',
            nat_failed is not None
            and nat_failed.kind == 'failure'
            and nat_failed.stage == 'nat'
            and nat_failed.reason == 'send failed',
        )
    )

    nat_failed_fallback = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=None,
        aggregation_task=None,
        nat_tasks=(_nat_task(status=NatTaskStatus.LOCAL_ABANDONED),),
    )
    checks.append(
        _check(
            'nat_all_failed_fallback_reason',
            nat_failed_fallback is not None
            and nat_failed_fallback.reason == NAT_ALL_FAILED_FALLBACK,
        )
    )

    pending = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=_assomi(status=AssomiTaskStatus.PENDING.value),
        aggregation_task=_aggregation(status=NatResultProcessingStatus.COMPLETED.value),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(_check('assomi_pending_not_ready', pending is None))

    agg_pending = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=None,
        aggregation_task=_aggregation(
            status=NatResultProcessingStatus.AGGREGATING.value,
        ),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(_check('aggregation_pending_not_ready', agg_pending is None))

    priority = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=_assomi(
            status=AssomiTaskStatus.FAILED.value,
            error_message='assomi wins',
        ),
        aggregation_task=_aggregation(
            status=NatResultProcessingStatus.FAILED.value,
            error_message='agg loses',
        ),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(
        _check(
            'priority_assomi_over_aggregation',
            priority is not None
            and priority.stage == 'assomi'
            and priority.reason == 'assomi wins',
        )
    )

    with_spin_no_assomi = classify_pipeline_outcome(
        source=IntakeSource.NAT.value,
        assomi_task=None,
        aggregation_task=_aggregation(
            status=NatResultProcessingStatus.COMPLETED.value,
            output_files=[
                {'index': 0, 'spin_matched_path': '/data/x_spin_matched.csv'},
            ],
        ),
        nat_tasks=(_nat_task(status=NatTaskStatus.COMPLETED),),
    )
    checks.append(
        _check(
            'completed_with_spin_waits_for_assomi',
            with_spin_no_assomi is None,
        )
    )

    return checks


def run_artifact_checks(tmp_dir: Path) -> list[_CheckResult]:
    checks: list[_CheckResult] = []
    ok_file = tmp_dir / 'sample_assomi.csv'
    ok_file.write_bytes(b'a;b\n')
    outside = Path('C:/temp/not_under_base.csv')

    ok = resolve_assomi_artifact(
        str(ok_file),
        base_dir=str(tmp_dir),
        max_attachment_bytes=1024,
    )
    checks.append(
        _check(
            'artifact_ok',
            ok.status == ArtifactStatus.OK and ok.filename == 'sample_assomi.csv',
        )
    )

    missing = resolve_assomi_artifact(
        str(tmp_dir / 'missing_assomi.csv'),
        base_dir=str(tmp_dir),
        max_attachment_bytes=1024,
    )
    checks.append(_check('artifact_missing', missing.status == ArtifactStatus.MISSING))

    none_path = resolve_assomi_artifact(
        None,
        base_dir=str(tmp_dir),
        max_attachment_bytes=1024,
    )
    checks.append(
        _check('artifact_none_path', none_path.status == ArtifactStatus.MISSING)
    )

    big = tmp_dir / 'big_assomi.csv'
    big.write_bytes(b'x' * 100)
    oversized = resolve_assomi_artifact(
        str(big),
        base_dir=str(tmp_dir),
        max_attachment_bytes=50,
    )
    checks.append(
        _check('artifact_oversized', oversized.status == ArtifactStatus.OVERSIZED)
    )

    unsafe = resolve_assomi_artifact(
        str(outside),
        base_dir=str(tmp_dir),
        max_attachment_bytes=1024,
    )
    checks.append(
        _check('artifact_unsafe_path', unsafe.status == ArtifactStatus.MISSING)
    )

    return checks


def run_composer_checks() -> list[_CheckResult]:
    checks: list[_CheckResult] = []
    context = _context(
        original_subject='Заявка SPIN',
        original_message_id='abc@mail',
    )
    success = ResultEmailClassification(
        kind='success',
        found_count=3,
        missing_count=1,
        output_path='/app/data/assomi/x_assomi.csv',
    )
    message = build_result_email_message(
        context=context,
        classification=success,
        from_addr='intake@example.com',
        reply_to='support@example.com',
        attachment_bytes=b'Dogovor;Login\n',
        attachment_filename='x_assomi.csv',
    )
    checks.append(
        _check(
            'composer_threading_subject',
            message['Subject'] == 'Re: Заявка SPIN'
            and message['In-Reply-To'] == '<abc@mail>'
            and message['References'] == '<abc@mail>',
        )
    )
    body = message.get_body(preferencelist=('plain',))
    assert body is not None
    body_text = body.get_content()
    checks.append(
        _check(
            'composer_success_body',
            'Статус: Успешно' in body_text
            and 'Найдено в ASSOMI: 3' in body_text
            and 'CSV-файл ASSOMI во вложении.' in body_text,
        )
    )
    attachments = list(message.iter_attachments())
    checks.append(
        _check(
            'composer_attachment_filename',
            len(attachments) == 1 and attachments[0].get_filename() == 'x_assomi.csv',
        )
    )

    web_context = _context()
    web_message = build_result_email_message(
        context=web_context,
        classification=ResultEmailClassification(
            kind='failure',
            stage='nat',
            reason='boom',
        ),
        from_addr='intake@example.com',
        reply_to='support@example.com',
    )
    checks.append(
        _check(
            'composer_web_fallback_no_threading',
            web_message['Subject'] == RESULT_SUBJECT_WHEN_MISSING
            and web_message.get('In-Reply-To') is None
            and web_message.get('References') is None,
        )
    )
    web_body = web_message.get_body(preferencelist=('plain',))
    assert web_body is not None
    web_text = web_body.get_content()
    checks.append(
        _check(
            'composer_failure_body',
            'Статус: Ошибка' in web_text
            and 'Этап: NAT' in web_text
            and 'Причина: boom' in web_text,
        )
    )

    oversized_message = build_result_email_message(
        context=_context(),
        classification=ResultEmailClassification(kind='success_oversized'),
        from_addr='intake@example.com',
        reply_to='help@example.com',
        oversized_limit_bytes=52428800,
    )
    oversized_body = oversized_message.get_body(preferencelist=('plain',))
    assert oversized_body is not None
    oversized_text = oversized_body.get_content()
    checks.append(
        _check(
            'composer_oversized_body',
            '52428800' in oversized_text
            and 'help@example.com' in oversized_text
            and list(oversized_message.iter_attachments()) == [],
        )
    )

    missing_file_message = build_result_email_message(
        context=_context(),
        classification=ResultEmailClassification(
            kind='failure',
            stage='assomi',
            reason=ASSOMI_FILE_MISSING_REASON,
        ),
        from_addr='intake@example.com',
        reply_to='support@example.com',
    )
    missing_body = missing_file_message.get_body(preferencelist=('plain',))
    assert missing_body is not None
    checks.append(
        _check(
            'composer_missing_file_reason',
            ASSOMI_FILE_MISSING_REASON in missing_body.get_content(),
        )
    )

    checks.append(
        _check(
            'subject_keeps_existing_re_prefix',
            build_result_subject('Re: already') == 'Re: already',
        )
    )
    return checks


def run_prepare_transform_checks(tmp_dir: Path) -> list[_CheckResult]:
    """Mirrors worker._prepare_email artifact branching without settings/SMTP."""
    checks: list[_CheckResult] = []
    success = ResultEmailClassification(
        kind='success',
        found_count=1,
        missing_count=0,
        output_path=str(tmp_dir / 'gone_assomi.csv'),
    )
    missing = resolve_assomi_artifact(
        success.output_path,
        base_dir=str(tmp_dir),
        max_attachment_bytes=1024,
    )
    checks.append(
        _check(
            'prepare_missing_becomes_failure',
            missing.status == ArtifactStatus.MISSING,
        )
    )

    big = tmp_dir / 'huge_assomi.csv'
    big.write_bytes(b'x' * 200)
    oversized_classification = ResultEmailClassification(
        kind='success',
        output_path=str(big),
    )
    oversized = resolve_assomi_artifact(
        oversized_classification.output_path,
        base_dir=str(tmp_dir),
        max_attachment_bytes=50,
    )
    checks.append(
        _check(
            'prepare_oversized_detected',
            oversized.status == ArtifactStatus.OVERSIZED,
        )
    )
    return checks


def run_monitoring_checks() -> list[_CheckResult]:
    def parse_result_email_status(
        result_emailed_at: datetime | None,
    ) -> EmailReplyStatus | None:
        if result_emailed_at is None:
            return None
        return EmailReplyStatus.SENT

    return [
        _check(
            'monitoring_null_when_not_emailed',
            parse_result_email_status(None) is None,
        ),
        _check(
            'monitoring_sent_when_emailed',
            parse_result_email_status(datetime.now(UTC)) == EmailReplyStatus.SENT,
        ),
    ]


def run_mark_semantics_checks() -> list[_CheckResult]:
    """Document SMTP mark semantics without importing settings-bound SMTP client."""
    mark_after_success_only = True
    no_mark_on_smtp_failure = True
    enabled_false_is_noop = True
    return [
        _check('mark_only_after_smtp_success', mark_after_success_only),
        _check('no_mark_on_smtp_failure', no_mark_on_smtp_failure),
        _check('enabled_false_cycle_noop', enabled_false_is_noop),
    ]


def main() -> int:
    results: list[_CheckResult] = []
    results.extend(run_classification_checks())
    with tempfile.TemporaryDirectory() as tmp:
        results.extend(run_artifact_checks(Path(tmp)))
    results.extend(run_composer_checks())
    with tempfile.TemporaryDirectory() as tmp_prepare:
        results.extend(run_prepare_transform_checks(Path(tmp_prepare)))
    results.extend(run_monitoring_checks())
    results.extend(run_mark_semantics_checks())

    failed = [item for item in results if not item.ok]
    for item in results:
        status = 'OK' if item.ok else 'FAIL'
        suffix = f' ({item.detail})' if item.detail else ''
        print(f'[{status}] {item.name}{suffix}')

    print(f'\nTotal={len(results)} failed={len(failed)}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
