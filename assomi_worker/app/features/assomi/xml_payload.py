from contextlib import suppress
from datetime import datetime
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo


def build_assomi_xml_payload(
    *,
    logins: list[str],
    branch: str,
    system: str,
    code_msg: int,
    name: str,
    is_test: bool,
    systime_timezone: ZoneInfo,
    systime_format: str,
    now: datetime | None = None,
) -> str:
    moment = now if now is not None else datetime.now(systime_timezone)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=systime_timezone)
    else:
        moment = moment.astimezone(systime_timezone)

    body = ET.Element('body')
    header = ET.SubElement(body, 'header')
    for field_name, field_value in (
        ('branch', branch),
        ('system', system),
        ('code_msg', str(code_msg)),
        ('name', name),
        ('isTest', '1' if is_test else '0'),
        ('sysTime', moment.strftime(systime_format)),
    ):
        element = ET.SubElement(header, field_name)
        element.text = field_value

    params = ET.SubElement(body, 'params')
    logins_element = ET.SubElement(params, 'logins')
    logins_element.text = ','.join(logins)

    with suppress(AttributeError):
        ET.indent(body, space='    ', level=0)

    encoded = ET.tostring(body, encoding='utf-8', xml_declaration=True)
    payload_bytes = (
        encoded if isinstance(encoded, bytes) else str(encoded).encode('utf-8')
    )
    return payload_bytes.decode('utf-8')
