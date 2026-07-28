from dataclasses import dataclass
from xml.etree import ElementTree as ET

from app.features.assomi.constants import ASSOMI_CODE_MSG_TAKEN_MESSAGE_MARKERS


@dataclass(frozen=True, slots=True)
class AssomiAbonent:
    contractnum: str
    login: str
    fio: str
    service_adress: str
    registration_adress: str


@dataclass(frozen=True, slots=True)
class AssomiBusinessError:
    error_code: str
    error_message: str
    code_msg: str | None


@dataclass(frozen=True, slots=True)
class AssomiAbonentInfo:
    abonents: tuple[AssomiAbonent, ...]


def is_code_msg_taken_error(error: AssomiBusinessError) -> bool:
    message = error.error_message.casefold()
    return any(
        marker.casefold() in message for marker in ASSOMI_CODE_MSG_TAKEN_MESSAGE_MARKERS
    )


def parse_assomi_response(
    response_text: str,
) -> AssomiAbonentInfo | AssomiBusinessError:
    xml_text = _extract_xml(response_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f'ASSOMI response is not valid XML: {exc}') from exc

    error = _find_business_error(root)
    if error is not None:
        return error

    abonents = _find_abonents(root)
    return AssomiAbonentInfo(abonents=tuple(abonents))


def _extract_xml(response_text: str) -> str:
    stripped = response_text.strip()
    if not stripped:
        raise ValueError('ASSOMI response body is empty')
    xml_start = stripped.find('<?xml')
    if xml_start == -1:
        xml_start = stripped.find('<')
    if xml_start == -1:
        raise ValueError('ASSOMI response does not contain XML')
    return stripped[xml_start:]


def _find_business_error(root: ET.Element) -> AssomiBusinessError | None:
    error_code = _find_text(root, 'Error_code')
    error_message = _find_text(root, 'Error_message')
    if error_code is None and error_message is None:
        return None
    return AssomiBusinessError(
        error_code=error_code or '',
        error_message=error_message or '',
        code_msg=_find_text(root, 'code_msg'),
    )


def _find_abonents(root: ET.Element) -> list[AssomiAbonent]:
    abonents: list[AssomiAbonent] = []
    for abonent in root.iter():
        if _local_name(abonent.tag) != 'Abonent':
            continue
        abonents.append(
            AssomiAbonent(
                contractnum=_child_text(abonent, 'contractnum'),
                login=_child_text(abonent, 'login'),
                fio=_child_text(abonent, 'fio'),
                service_adress=_child_text(abonent, 'service_adress'),
                registration_adress=_child_text(abonent, 'registration_adress'),
            )
        )
    return abonents


def _find_text(root: ET.Element, tag_name: str) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) == tag_name and element.text is not None:
            text = element.text.strip()
            if text:
                return text
    return None


def _child_text(parent: ET.Element, tag_name: str) -> str:
    for child in list(parent):
        if _local_name(child.tag) == tag_name:
            return (child.text or '').strip()
    return ''


def _local_name(tag: str) -> str:
    if '}' in tag:
        return tag.rsplit('}', maxsplit=1)[-1]
    return tag
