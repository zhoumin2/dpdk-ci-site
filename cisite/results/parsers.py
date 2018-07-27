"""Define parsers for results API."""

import json
from rest_framework.parsers import MultiPartParser, ParseError


class JSONMultiPartParser(MultiPartParser):
    """Parse multipart/form-data with a 'json' field containing metadata.

    Taken with modifications from https://stackoverflow.com/a/29202797
    """

    media_type = 'multipart/form-data'

    def parse(self, stream, media_type, parser_context):
        """Parse the request and return a DataAndFiles object."""

        result = super().parse(stream, media_type, parser_context)

        try:
            result.data = result.data.copy()
            jsonlist = result.data.pop('json')
            if len(jsonlist) != 1:
                raise ParseError(f'JSON parse error - too many json keys')
            jsonData = json.loads(jsonlist[0])

            if result.data:
                raise ParseError(f'Extra request keys - {jsonData.keys()}')
            for k, v in jsonData.items():
                if isinstance(v, list):
                    result.data.setlist(k, v)
                else:
                    result.data[k] = v

            for k in result.files.keys():
                jsonData[k] = result.files[k]
            return jsonData
        except Exception as exc:
            raise ParseError(f'JSON parse error - {str(exc)}')
