# Lançamento Instagram Best Creations — 7 Stories + 20 posts

Status: **automação implementada e testada offline; não publicada, não ativada**.

Conta fixada no código: **@bestcreations011**. Sequência obrigatória: **7 Stories primeiro**, depois **20 fotos do feed**. O PDF Reader foi substituído pelo Cantinho do Luiz, conforme o pacote de lançamento.

## 1. Importar as 27 imagens uma única vez

O pacote preparado no ChatGPT tem o nome exato:

`best_creations_publicacao_stories_feed.zip`

Ele contém as 27 imagens JPEG e o `manifesto_publicacao.json` com a ordem e as legendas.

1. No GitHub, abra **BMatheus1/best-creations-instagram → Releases → Draft a new release**.
2. Escolha uma tag, por exemplo `bc-launch-2026-11`. Anexe `best_creations_publicacao_stories_feed.zip`. Publique a Release.
   - **Atenção:** esta é uma Release de um repositório público: seu ZIP ficará publicamente acessível. O pacote contém artes destinadas à divulgação, não tokens ou documentos privados.
3. Abra **Actions → Importar pacote de lancamento (sem publicar) → Run workflow** (branch `main`).
4. Preencha:
   - `release_tag`: a tag escolhida (por exemplo `bc-launch-2026-11`).
   - `confirm`: `IMPORTAR_27_ARTES`.
5. O workflow valida os nomes, tamanhos, proporções, a estrutura do ZIP, a conta, a ordem e as imagens; grava os arquivos em `media/launch/` e a fila em `content/launch_queue.json`.
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
3. O workflow verifica a fila nos minutos **13, 28, 43 e 58** de cada hora. Horários em UTC.
4. É publicado, no máximo, **um item por execução**; a fila exige intervalos:
   - Stories: pelo menos **15 minutos** entre Stories.
   - Primeiro post do feed: pelo menos **60 minutos** após o último Story.
   - Próximos posts do feed: pelo menos **12 horas** entre fotos.
5. Desative novamente mudando essa variável para `false` (ou removendo-a).

O GitHub Actions pode atrasar execuções agendadas e não garante o minuto exato. A automação não usa disparos em massa, não publica Stories repetidos e respeita interrupções.

A variável antiga `INSTAGRAM_AUTO_PUBLISH_ENABLED` pertence ao publicador inicial de fotos e **não controla este lançamento**.

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

Depois do ZIP: fila completa com 27 imagens e legendas, ainda sem publicações.

Após ativar: primeiros 7 Stories, então 20 fotos do feed; os **Destaques permanecem etapa manual no Instagram**.

**Esta integração ainda não prova publicação efetiva na Meta.** Esse teste só acontecerá quando a conta, o token e os arquivos públicos forem verificados numa execução autorizada.
