# Lançamento Instagram Best Creations — 7 Stories + 20 posts

Status: **27 artes importadas; primeiro Story confirmado pela API em 02/11/2026. Publicação automática ativada via variável do GitHub, com execução contínua como alternativa aos disparos atrasados ou perdidos do cron.**

Conta fixada no código: **@bestcreations011**. Sequência obrigatória: **7 Stories primeiro**, depois **20 fotos do feed**. O PDF Reader foi substituído pelo Cantinho do Luiz, conforme o pacote de lançamento.

## 1. Importar as 27 imagens uma única vez

O pacote preparado no ChatGPT tem o nome exato:

`Best_Creations_Instagram_Lancamento_27_Artes.zip` (ou outro nome `.zip`; o importador procura um único ZIP na Release)

Ele contém as 27 imagens JPEG e o `manifesto_publicacao.json` com a ordem e as legendas.

1. No GitHub, abra **BMatheus1/best-creations-instagram → Releases → Draft a new release**.
2. Use a Release **já criada** com a tag `bc-launch-2026-11` e seu anexo `Best_Creations_Instagram_Lancamento_27_Artes.zip`. **Não precisa criar outra Release nem reenviar o ZIP**. Se começar do zero, anexe um único ZIP válido.
   - **Atenção:** esta é uma Release de um repositório público: seu ZIP ficará publicamente acessível. O pacote contém artes destinadas à divulgação, não tokens ou documentos privados.
3. Abra **Actions → Importar pacote de lancamento (sem publicar) → Run workflow** (branch `main`).
4. Preencha:
   - `release_tag`: a tag escolhida (por exemplo `bc-launch-2026-11`).
   - `confirm`: `IMPORTAR_27_ARTES`.
5. O workflow identifica o único ZIP na Release independentemente do nome, valida os nomes, tamanhos, proporções, a estrutura, a conta, a ordem e as imagens; grava os arquivos em `media/launch/` e a fila em `content/launch_queue.json`.
6. **A importação não publica nada**. O workflow falha se já houver tentativas registradas no histórico.

Se o workflow não puder fazer `git push`, confira **Settings → Actions → General → Workflow permissions** e habilite permissão para gravar conteúdo (somente se adequado à sua política do repositório). GitHub Actions precisa de `contents: write` para registrar as imagens e o histórico.

## 2. Verificar antes de publicar

1. Confira as imagens e respectivas legendas geradas em `content/launch_queue.json`. Observe especialmente o carácter experimental dos conceitos, pilotos e projetos acadêmicos; os mockups não representam métricas verdadeiras.
2. Abra **Actions → Verificar conexao Instagram**, rode o teste de leitura do perfil e confirme que a conta é `@bestcreations011`.
3. Abra **Actions → Lancamento Instagram - Stories e Feed → Run workflow** e selecione `dry-run`. Confirmação em branco.
4. O dry-run verifica os arquivos e a ordem. Nenhuma mídia é criada na Meta.

## 3. Publicar um item manualmente (sem repetição)

Em **Actions → Lancamento Instagram - Stories e Feed → Run workflow**:

- `action`: `publish-next`
- `confirm`: `PUBLICAR_PROXIMO`

Cada execução publica **somente o próximo item**, respeitando a ordem e o intervalo mínimo.

O Workflow utiliza o Secret já existente `INSTAGRAM_ACCESS_TOKEN`, que deve continuar válido e ter `instagram_business_basic` + `instagram_business_content_publish` e acesso à conta Business `@bestcreations011`.

O código envia Stories via `POST /{ig-id}/media` com `media_type=STORIES`, depois `POST /{ig-id}/media_publish`. Para fotos do feed utiliza `image_url` + `caption`. Uma URL HTTPS pública dos JPEGs é necessária para a Meta importar a mídia.

**Limitação:** a API não permite adicionar automaticamente os Stories aos **Destaques**. Após a publicação de cada Story, abra o Instagram e inclua-o no Destaque desejado (Sobre, Orçamento, Apps, Design, Sistemas e Sites). Faça isso enquanto o Story estiver disponível, ou use o arquivo de Stories quando habilitado.

## 4. Ativar a publicação automática (opt-in)

Por padrão **NADA é publicado automaticamente**.

Depois da importação, revisão e dry-run aprovados, se desejar que a sequência prossiga sem confirmação em cada execução:

1. Entre em **Settings → Secrets and variables → Actions → Variables**.
2. Crie ou altere **`INSTAGRAM_LAUNCH_AUTO_PUBLISH_ENABLED` = `true`**.
3. Há dois mecanismos de continuidade:
   - **Lote contínuo**: o workflow é acionado uma vez com autorização e segue a fila em uma única execução do GitHub Actions, publicando **uma mídia por vez com pelo menos 5 minutos após a publicação anterior**. Assim não depende de agendamentos periódicos para cada conteúdo. O limite da execução é 210 minutos.
   - **Cron de contingência**: `*/5 * * * *` (UTC). A cada disparo, publica no máximo um item pendente. O GitHub Actions pode atrasar ou omitir esses disparos; **não é uma garantia de entrega**.
4. A fila exige sempre o mesmo intervalo mínimo:
   - Stories: **5 minutos**.
   - Primeiro feed após o último Story: **5 minutos**.
   - Feed para feed: **5 minutos**.
5. Para impedir novos disparos, altere a variável `INSTAGRAM_LAUNCH_AUTO_PUBLISH_ENABLED` para `false`. **IMPORTANTE: para interromper um lote já em execução, cancele o job na aba Actions**; variáveis são capturadas no início e alterar `true` para `false` não interrompe uma execução já iniciada.

O lote é ativado apenas quando a variável está `true` e houver uma execução explicitamente iniciada (commit marcado `[start-launch-batch]` ou despacho manual `publish-batch` com `PUBLICAR_LOTE`). Cada item fica registrado como tentativa antes do envio à Meta; erro ou resultado ambíguo interrompe o lote sem repetição automática.

A variável antiga `INSTAGRAM_AUTO_PUBLISH_ENABLED` pertence ao publicador inicial de fotos e **não controla este lançamento**; mantenha desativada para evitar concorrência.

### Lançamento acelerado (alteração de 02/11/2026)

O responsável solicitou intervalo mais curto: a fila mantém as 27 publicações separadas em ordem e agora aplica **5 minutos mínimos entre conteúdos**. O cron do GitHub Actions sozinho não iniciou as próximas publicações após sua ativação; o modo de lote contínuo corrige essa dependência. Se a API aceitar e a execução permanecer ativa, os 26 itens restantes podem levar cerca de **2h10**, além do tempo de processamento; erros, limites da Meta e atrasos podem prolongar. A publicação em massa de 20 fotos no feed em pouco tempo **pode prejudicar o alcance ou ser entendida como comportamento excessivo pela plataforma**. Esta é uma configuração de lançamento excepcional, não recomendada como cadência editorial recorrente.

Não crie nova Release e não importe novamente: o primeiro Story está registrado como publicado em `state/launch_publications.json`. Ativar apenas `INSTAGRAM_LAUNCH_AUTO_PUBLISH_ENABLED=true` no GitHub após revisar o ritmo desejado. A nova configuração **não reenvia** o primeiro Story.

## 5. Proteções contra falhas

- A conta é verificada pela API **antes** de qualquer tentativa.
- Para Stories, o código exige `account_type=BUSINESS`. Se a conta não corresponder, a publicação é bloqueada.
- O arquivo JPEG é validado localmente por SHA-256 e conferido na URL pública.
- Histórico: `state/launch_publications.json` (separado do histórico do publicador antigo).
- **O bloqueio da tentativa é salvo e enviado ao GitHub antes do POST de mídia.** Falha ou resultado ambíguo **não gera reenvio automático**.
- Se o histórico ficar em `attempt_started`, `container_created` ou `publish_requested`, a fila inteira para até revisão manual.
- Os workflow runs usam o mesmo bloqueio de concorrência para não publicar simultaneamente.
- Nunca envie token ou segredo ao chat, Release ou código-fonte.
- O **preview é ilustrativo**: os valores nos painéis e indicadores não são dados de clientes.

## Arquivos principais

| Arquivo | Função |
| --- | --- |
| `.github/workflows/import-launch-assets.yml` | Importa o ZIP de uma Release, sem enviar mídia à Meta |
| `scripts/import_launch_assets.py` | Valida 27 imagens e cria a fila |
| `.github/workflows/publish-launch.yml` | Dry-run, próxima publicação, agendamento opt-in |
| `scripts/publish_launch.py` | Envio controlado, pacing, prevenção de duplicatas |
| `tests/test_launch_automation.py` | Testes simulados sem token nem chamadas Meta |
| `state/launch_publications.json` | Registro permanente de tentativas |
| `content/launch_queue.json` | Gerado automaticamente na importação |

## Estado esperado

Antes do ZIP: histórico vazio, sem fila pronta, publicação desativada.

Depois do ZIP: fila completa com 27 imagens e legendas.

Estado verificado em 02/11/2026: primeiro Story publicado; 26 pendentes no histórico.

Após ativar: seis Stories restantes, então 20 fotos do feed; os **Destaques permanecem etapa manual no Instagram**.

**A publicação do primeiro Story foi confirmada na API Meta em 02/11/2026**, com identificador persistido em `state/launch_publications.json`. As demais publicações precisam de confirmação individual no histórico. Não considerar sucesso de CI offline como confirmação de publicação.

## Correção confirmada em 02/11/2026

A Release `bc-launch-2026-11` já foi criada corretamente com o ZIP `Best_Creations_Instagram_Lancamento_27_Artes.zip` (5,9 MB). A execução de importação falhou em **Baixar ZIP do Release informado** porque o script antigo buscava o nome `best_creations_publicacao_stories_feed.zip`: o GitHub retornou `no assets match the file pattern`. O importador agora aceita qualquer **único** ZIP da Release. Os testes antigos também passaram a instalar Pillow antes de executar toda a suíte; a ausência da biblioteca causava quatro falhas independentes.

**Para repetir:** Actions → Importar pacote de lancamento (sem publicar) → Run workflow → branch main → `release_tag: bc-launch-2026-11` → `confirm: IMPORTAR_27_ARTES`. Depois confira se a fila `content/launch_queue.json` existe e execute `dry-run`. **Não ative a variável de publicação automática antes de revisar o primeiro Story e testar a API.**

## Cancelamento de oito posts institucionais do feed (02/11/2026)

Por solicitação do responsável, as posições **2 a 9 do feed** foram retiradas da **fila ativa de publicação**, IDs `bc-launch-009` a `bc-launch-016`. A lista de exclusão é `content/launch_exclusions.json`, aplicada por `scripts/publish_launch.py` tanto em publicação manual quanto automática; as artes e metadados originais permanecem arquivados para auditoria e não são reenviados. O post 2 do feed (`bc-launch-009`, “Institucional 01”) **já havia sido publicado** às 14h13 (Brasília) quando a solicitação chegou; removê-lo do Instagram exige exclusão pelo usuário na plataforma. Os posts 3 a 9 ainda não haviam sido publicados.

O próximo item autorizado, depois das publicações já registradas, passa a ser **`bc-launch-017` — feed 10, “Institucional 09”**. O histórico de posts publicados jamais é apagado. A execução contínua anterior foi cancelada e a fila editada antes de reiniciar; nenhuma publicação deve ser repetida.
