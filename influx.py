import time

import attrs
import requests


name_validator = attrs.validators.matches_re("[a-zA-Z][_a-zA-Z]*")


def render_item(key, value):
    if isinstance(value, str):
        formatted = '"{}"'.format(value.replace('"', r'\"'))
    elif isinstance(value, bool):
        formatted = 'true' if value else 'false'
    elif isinstance(value, int):
        if (value - 1 if value < 0 else 0).bit_length() > 63:
            formatted = format(value, "e")
        formatted = f"{value:d}i"
    elif isinstance(value, float):
        formatted = format(value, "e")
    else:
        raise TypeError("unsupported value type", type(value))

    return f"{key}={formatted}"


@attrs.define()
class Point:
    measurement: str = attrs.field(validator=name_validator)

    fields: dict[str, float | int | str | bool] = attrs.field(
        validator=attrs.validators.deep_mapping(
            key_validator=name_validator,
            value_validator=attrs.validators.instance_of((float, int, str, bool)),
        )
    )
    tags: dict[str, str] = attrs.field(
        factory=dict,
        validator=attrs.validators.deep_mapping(
            key_validator=name_validator,
            value_validator=attrs.validators.instance_of(str),
        )
    )

    time: int = attrs.field(factory=time.time_ns)

    def _render_tags(self) -> str:
        if not self.tags:
            return ""
        tags = ",".join(render_item(*tag) for tag in self.tags.items())
        return f",{tags}"

    def _render_fields(self) -> str:
        return ",".join(render_item(*tag) for tag in self.fields.items())

    def as_line(self) -> str:
        return "{}{} {} {}\n".format(
            self.measurement,
            self._render_tags(),
            self._render_fields(),
            self.time,
        )


class Client:
    def __init__(self, *, base_url, org=None, bucket=None, token=None):
        self.base_url = base_url
        self.org = org
        self.bucket = bucket
        self.token = token

    def write_points(self, points: list[Point], *, org=None, bucket=None):
        if org is None:
            org = self.org
        if bucket is None:
            bucket = self.bucket
        if org is None:
            raise ValueError("no org specified, no default")
        if bucket is None:
            raise ValueError("no bucket specified, no default")

        headers = {
            "Content-Type": "text/plain",
            "Accept": "application/json",
        }
        if self.token:
            # feels like it should be 'Bearer', but nope, 'Token'
            headers["Authorization"] = f"Token {self.token}"

        params = {
            "org": org,
            "bucket": bucket,
            "precision": "ns",
        }

        resp = requests.post(
            url=self.base_url + "/api/v2/write",
            headers=headers,
            params=params,
            data="".join(p.as_line() for p in points),
        )
        resp.raise_for_status()
        return resp
