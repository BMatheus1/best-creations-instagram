"""Diagnóstico seguro da conexão Instagram API with Instagram Login.

Só consulta GET /me. Nunca publica, nunca exibe token, corpo bruto ou headers.
Compara a rota usada no publicador (v24.0) com /me sem versão.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

INSTAGRAM_API_BASE = "https://graph.instagram.com"
TARGET_ACCOUNT = "bestcreations011"
FIELDS = "id,user_id,username,account_type"


def safe_meta_codes(body):
    """Extrai apenas os códigos numéricos, não mensagens ou dados privados."""
    try:
        parsed = json.loads(body)
        err = parsed.get("error", {})
        if not isinstance(err, dict):
            return None, None
        code, subcode = err.get("code"), err.get("error_subcode")
        if type(code) is not int or not (0 <= code <= 10000):
            code = None
        if type(subcode) is not int or not (0 <= subcode <= 100000):
            subcode = None
        return code, subcode
    except (ValueError, TypeError, AttributeError):
        return None, None


def read_profile(token, version):
    params = urllib.parse.urlencode({"fields": FIELDS})
    url = f"{INSTAGRAM_API_BASE}/{version + '/' if version else ''}me?{params}"
    request = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response), None
    except urllib.error.HTTPError as exc:
        code, subcode = safe_meta_codes(exc.read(4096))
        return None, (exc.code, code, subcode)
    except (urllib.error.URLError, TimeoutError):
        return None, ("network", None, None)
    except (ValueError, json.JSONDecodeError):
        return None, ("response", None, None)


def print_failure(label, error):
    if error[0] == "network":
        print(f"{label}: falha de rede; confira acesso externo do runner.")
        return
    if error[0] == "response":
        print(f"{label}: resposta inválida da API.")
        return
    http, code, subcode = error
    details = f"HTTP {http}"
    if code is not None:
        details += f"; código Meta {code}"
    if subcode is not None:
        details += f"; subcódigo {subcode}"
    print(f"{label}: autenticação ou chamada recusada ({details}).")


def validate_profile(profile):
    if not isinstance(profile, dict) or not profile.get("id"):
        print("Resposta da API sem ID de perfil.")
        return False
    username = str(profile.get("username", ""))
    if username.casefold() != TARGET_ACCOUNT:
        print("BLOQUEADO: token conectado a outra conta. Esperada @bestcreations011.")
        return False
    print("CONEXÃO COM O INSTAGRAM: OK")
    print("Conta: @" + username)
    account_type = str(profile.get("account_type", "não informado")).upper()
    print("Tipo: " + account_type)
    if account_type != "BUSINESS":
        print("ATENÇÃO: Story via API exige conta Business; lançamento bloqueado até validar.")
        return False
    print("A conta e o perfil Business estão corretos. Nenhuma publicação realizada.")
    return True


def main():
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        print("SECRET AUSENTE: configure INSTAGRAM_ACCESS_TOKEN em GitHub Settings → Actions → Secrets.")
        return 1

    # A mesma rota versão 24.0 que scripts/publish_launch.py usa.
    profile, error = read_profile(token, "v24.0")
    if profile is not None:
        return 0 if validate_profile(profile) else 1

    print_failure("Instagram API v24.0 /me", error)
    # Se a consulta de controle sem versão funcionar, não é necessário
    # reautorizar às cegas: precisamos revisar a versão da API.
    control_profile, control_error = read_profile(token, "")
    if control_profile is not None:
        print("DIAGNÓSTICO: /me sem versão funciona, mas v24.0 falhou.")
        print("Não substitua o token antes de corrigir a versão da API no publicador.")
        validate_profile(control_profile)
        return 1
    print_failure("Instagram API /me sem versão", control_error)
    if error[0] == 401 or control_error[0] == 401:
        print("AÇÃO: gere um novo token do Instagram Login, autorize @bestcreations011 e atualize")
        print("o Secret INSTAGRAM_ACCESS_TOKEN. Nunca cole o token em logs, Release ou conversa.")
        print("Depois rode este workflow novamente; não tente publish-next ainda.")
    else:
        print("A API recusou a conexão; revise permissões da Meta e status do app.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
