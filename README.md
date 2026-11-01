# best-creations-instagram
Materiais de divulgação da Best Creations

## Automatização do lançamento (Stories + Feed)

O novo fluxo de lançamento está pronto no código e possui validações automatizadas:

- Importação do ZIP com **7 Stories e 20 fotos**, pela aba **Actions**, sem publicar na Meta.
- Publicação na sequência exata; Stories antes dos posts.
- Teste (dry-run) sem credenciais; acionamento manual e agendamento opcional.
- Proteção por hash, conta @bestcreations011 e histórico anti-duplicação.
- Agendamento automático **desativado por padrão**; os Destaques ainda devem ser organizados no Instagram.

**[Leia o passo a passo completo](LAUNCH_AUTOMATION.md)**.

A autenticação da Meta e as permissões podem impedir publicações reais mesmo após testes offline bem-sucedidos. O pipeline não confirma postagens sem o retorno da API.
