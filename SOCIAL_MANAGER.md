# Best Creations Instagram Manager

Gerenciador inicial de conteúdo da **@bestcreations011**.

## Segurança atual

**Somente simulação.** O módulo NÃO publica no Instagram, NÃO acessa tokens e NÃO altera o perfil.
Nenhuma publicação sai automaticamente do GitHub. O Secret `INSTAGRAM_ACCESS_TOKEN` permanece reservado para os próximos módulos.

## Conteúdo

- `content/queue.json`: lista de publicações; o conteúdo de exemplo começa em `draft`.
- `scripts/social_manager.py`: valida tipos, URLs, aprovações e fusos horários e simula publicações previstas.
- `tests/test_social_manager.py`: testes de segurança e validação.
- `.github/workflows/simulate-publications.yml`: testes automatizados e simulação sem credenciais.

## Estados

- `draft`: rascunho; nunca elegível.
- `approved`: precisa `approved_by: "owner"` e `scheduled_at` em ISO 8601 com fuso. Neste módulo apenas simula elegibilidade.
- `cancelled`: ignorado.
- `published`: ignorado.

## Executar

No GitHub: **Actions → Simular fila de publicacoes → Run workflow**.

Localmente:

```bash
python -m unittest discover -s tests -v
python scripts/social_manager.py --dry-run
```

## Próximos módulos

Após validação do fluxo, será implementado um publicador para Instagram Business Login com controle manual de ativação, prevenção de duplicação, logs e agendamento. Publicações reais exigirão confirmação explícita antes da ativação.

**Repositório público:** não coloque tokens, senhas, dados privados de clientes ou arquivos `.env` aqui.
