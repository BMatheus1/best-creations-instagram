# Publicador real — Instagram Business Login

## Status

O publicador está implementado, mas **nenhuma publicação foi enviada ao Instagram**.
O agendamento automático está **DESATIVADO por padrão**.
O exemplo `bc-post-001` permanece como `draft`, com imagem PNG — não pode ser publicado até que haja um JPEG e aprovação explícita.

## Como preparar um post

Em `content/queue.json`:

- `type`: `IMAGE` (outros formatos ainda não suportados pelo publicador real)
- `media_urls`: uma URL HTTPS acessível publicamente, para JPEG (.jpg ou .jpeg)
- `caption`: legenda até 2200 caracteres
- `status`: `approved`, **somente após autorização do dono**
- `approved_by`: `owner`
- `scheduled_at`: ISO 8601 com fuso, ex.: `2026-10-25T10:00:00-03:00`

O arquivo `state/publications.json` mantém um bloqueio persistente. Não apague entradas para tentar republicar; cada post deve receber um ID novo apenas quando o proprietário solicitar uma nova publicação.

## Publicação manual explícita

GitHub → Actions → **Publicar foto no Instagram (controle seguro)** → **Run workflow**.

Preencha `post_id` e confirme com o texto exato `PUBLICAR:<post_id>`.

A execução exige um item aprovado, data atingida, JPEG, conta @bestcreations011 e token do Secret. Registra a tentativa no GitHub ANTES de criar mídia. A publicação não é repetida automaticamente; em falhas verifique os registros e o Instagram.

## Agendamento automático (futuro)

O workflow faz verificações a cada 15 minutos, mas **não publica** até ativarmos explicitamente a variável de repositório `INSTAGRAM_AUTO_PUBLISH_ENABLED=true` em Settings → Secrets and variables → Actions → Variables.

Após isso, itens `approved` vencidos podem ser publicados sem nova confirmação individual de execução. O agendamento via GitHub Actions é aproximado e pode atrasar; será no máximo 1 post por execução.

**Nunca ative a variável sem o aval do proprietário.**

## Limitações

- Somente fotos JPEG únicas no feed nesta versão. Não publica Stories, Reels ou carrosséis.
- Nenhuma alteração de bio, avatar ou destaques.
- Evite configurar Secrets em repositório público fora do GitHub Actions Secrets.
- O token do Instagram deve ter permissão `instagram_business_content_publish`.
- Em falhas após iniciar uma publicação o histórico bloqueia novas tentativas do mesmo ID, exigindo revisão humana.
- Uma falha entre o POST e o commit final pode deixar o estado como `publish_requested`; verifique o feed antes de concluir qualquer nova ação.
