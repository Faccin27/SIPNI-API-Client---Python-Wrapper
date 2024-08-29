import base64
import json
import time
from urllib.parse import quote

import httpx
import stamina


class UnexpectedHTTPResponseException(Exception):
    ...


class UnauthorizedException(Exception):
    ...


class SIPNI:
    def __init__(self, login: str, password: str, autologin=True):
        default_headers = {
            'User-Agent': (
                'Mozilla/5.0 (U; Windows i576 x86_64; pt-BR) '
                'Gecko/20100101 Firefox/51.5'
            )
        }

        self.autologin = autologin

        self._http_session = httpx.Client(
            base_url='https://servicos-cloud.saude.gov.br',
            headers=default_headers
        )

        self._basic_authorization = (
            base64.b64encode(f'{login}:{password}'.encode()).decode()
        )

        self.authorize()

    @staticmethod
    def _autologin_decorator(function):
        def decorator(self, *args, **kwargs):
            if self.autologin:
                _, payload, _ = self._access_token.split('.')
                payload = json.loads(base64.b64decode(payload + '==='))
                if payload['exp'] <= time.time():
                    self.authorize()
            return function(self, *args, **kwargs)
        return decorator

    @stamina.retry(on=httpx.ReadTimeout, attempts=5)
    def authorize(self):
        request = self._http_session.post(
            url='/pni-bff/v1/autenticacao/tokenAcesso',
            headers={'X-Authorization': f'Basic {self._basic_authorization}'}
        )

        response = request.json()

        if request.status_code != 200:
            exception = UnexpectedHTTPResponseException

            if response['erro-mensagem'] == 'Authentication':
                exception = UnauthorizedException

            raise exception(response)

        self._access_token = response['accessToken']
        self._header_bearer_authorization = dict(
            Authorization=f"Bearer {self._access_token}"
        )

        return True

    @_autologin_decorator
    @stamina.retry(on=httpx.ReadTimeout, attempts=5)
    def query(self, document: str):
        personal_information = self._http_session.get(
            url='/pni-bff/v1/cidadao/cpf/' + quote(document),
            headers=self._header_bearer_authorization
        ).json()

        calendary_information = self._http_session.get(
            url='/pni-bff/v1/calendario/cpf/' + quote(document),
            headers=self._header_bearer_authorization
        ).json()

        return dict(
            pessoal=personal_information,
            calendario=calendary_information
        )


if __name__ == '__main__':
    import dotenv
    environment = dotenv.dotenv_values()

    sipni = SIPNI(
        login=environment['SIPNI_LOGIN'],
        password=environment['SIPNI_PASSWORD']
    )

    print(sipni.query('03709375975'))