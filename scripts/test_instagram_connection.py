"""Teste somente leitura da conexão oficial Instagram Business Login.

Nunca publica conteúdo. O token vem exclusivamente do GitHub Actions Secret.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main() -> int:
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERRO: Secret INSTAGRAM_ACCESS_TOKEN não está configurado.")
        return 1

    # Não inclua o token na URL ou em logs. A rota /me só lê o perfil.
    params = urllib.parse.urlencode({"fields": "id,user_id,username,account_type"})
    url = "https://graph.instagram.com/me?" + params
    request = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            profile = json.load(response)
    except urllib.error.HTTPError as exc:
        # Não exibe corpo de erro, headers, token nem URL completa.
        print(f"Falha na autenticação/API: HTTP {exc.code}.")
        print("Confira o token de Instagram Login e as permissões do aplicativo.")
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Falha de rede ao consultar a API: {type(exc).__name__}.")
        return 1
    except (ValueError, json.JSONDecodeError):
        print("A API retornou uma resposta inválida.")
        return 1

    username = profile.get("username")
    account_type = profile.get("account_type")
    if not username:
        print("A API respondeu sem username; confira permissões.")
        return 1

    print("CONEXÃO COM O INSTAGRAM: OK")
    print("Conta:", "@" + str(username))
    print("Tipo:", account_type or "não informado")
    print("ID do Instagram:", profile.get("user_id") or profile.get("id") or "não informado")
    if str(username).lower() != "bestcreations011":
        print("ATENÇÃO: token pertence a uma conta diferente da @bestcreations011.")
        return 1
    print("Teste finalizado. Nenhuma publicação foi realizada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
