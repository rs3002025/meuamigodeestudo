# Avaliação Completa do Sistema "Amigo de Estudo" (MVP)

Abaixo segue minha avaliação "sem filtro" sobre o projeto, sua arquitetura atual, pontos críticos de segurança (incluindo o vazamento detectado na sua solicitação inicial), e recomendações de como evoluir esse MVP para um produto real.

---

## 1. Visão Geral da Arquitetura
O sistema é um backend em **Python (Flask)** projetado como um MVP de estudo guiado ("zero decisão").
*   **Rotas e Serviços:** A estrutura separa bem a camada de transporte (Flask Blueprints na pasta `/routes`) da lógica de negócios (módulos isolados na pasta `/services`).
*   **Persistência (O Gargalo Inicial):** Todo o estado do sistema está rodando através de uma estrutura de dicionários em memória (`services/db.py`). Embora haja um pacote `psycopg` no `requirements.txt` e uma verificação para a variável `DATABASE_URL`, o código atual não está de fato escrevendo no PostgreSQL.
*   **Integração de IA:** Existe um uso de IA (`services/ia_service.py`) batendo diretamente na OpenAI (`gpt-4.1-mini`), com mecanismos bem bolados de fallback local e um limite "free" (3 requisições diárias), gerenciado via cache de memória.

## 2. Críticas "Sem Filtro"

### A. Segurança Crítica: Vazamento da Chave do Banco
Na sua mensagem inicial, você colou uma string de conexão de produção do banco Railway com credenciais de superusuário (`postgres`) e senha em texto plano, exposto através do proxy público (`switchyard.proxy.rlwy.net`).
**Por que isso é terrível?**
Qualquer pessoa que tenha acesso ao seu histórico, repositório ou log onde isso foi postado pode conectar no seu banco e sequestrá-lo, apagá-lo, ou usá-lo para mineração/ataques.
*   **O que fazer:** Rotacione (mude) a senha do banco imediatamente no painel da Railway.
*   **Como evitar:** Nunca escreva URIs com senhas no código, em mensagens do Slack/Discord/WhatsApp ou em prompts de IA. Sempre use Variáveis de Ambiente (`os.getenv("DATABASE_URL")`).

### B. Persistência Baseada em Memória (O Problema do MVP)
O `services/db.py` é uma classe `MemoryDB`.
*   O sistema no Railway funciona em containers (ou dynos) efêmeros. Isso significa que **toda vez que você faz deploy, o servidor reinicia ou escala**, todo o progresso dos usuários (usuários, planos, tarefas, métricas, cache de IA) é **completamente apagado**.
*   **Ação Mínima Viável:** Você precisa substituir o `MemoryDB` por consultas reais usando o driver `psycopg` com conexão ao banco de dados Railway. Use bibliotecas de migração (ex: `Alembic`) ou um ORM leve (como `SQLAlchemy`) para gerenciar as tabelas.

### C. Chamadas Síncronas (Bloqueantes) de IA
O `ia_service.py` usa `urllib.request.urlopen` (que é síncrono e bloqueante) com um timeout de 20 segundos para bater na OpenAI.
*   Como o Flask roda por padrão com *workers* síncronos, se 5 pessoas pedirem uma tarefa ao mesmo tempo e a OpenAI demorar 15 segundos para responder, seu servidor vai travar para todos os outros usuários.
*   **Recomendação:** A geração de tarefas deve ser preferencialmente assíncrona (usando bibliotecas como `httpx`, `asyncio` e migrando de Flask para FastAPI/Quart, ou rodando a tarefa em background via Celery/RQ com uma notificação ao frontend via polling ou WebSocket).

### D. Organização da Geração de "Fake Data" (Fallbacks)
O fallback (`_fallback_conteudo`) e as gerações automáticas de listas evitam a quebra da aplicação, o que é ótimo para o usuário final, mas os mocks são bastante estáticos (ex: as três matérias vão sempre ser "frações, equações, problemas práticos" se for matemática). No longo prazo, a repetitividade causará churn.

---

## 3. Ideias de Implantação e Melhorias (Escalando o MVP)

Se a ideia é transformar este MVP em um produto comercial ou que receba tráfego real, siga esse plano de evolução:

**Fase 1: Estabilidade Imediata**
1.  **Integração Real com o Banco:** Altere `services/db.py` para usar de fato o PostgreSQL configurado no Railway em vez de dicionários Python.
2.  **Segurança de API Keys:** Certifique-se de que a `OPENAI_API_KEY` e a `DATABASE_URL` estão sendo fornecidas exclusivamente pelo painel do Railway (Variáveis de Ambiente), jamais commitadas.
3.  **Logs:** Implemente `logging` em vez de retornos silenciosos ou `print()`. Quando a IA falhar ou o banco de dados cair, você precisa de logs claros do porquê (por exemplo, erro de JSON na IA é tratado de forma silenciosa e vira fallback).

**Fase 2: Arquitetura e Performance**
1.  **Caching via Redis:** O cache de conteúdo no `MemoryDB` não funciona entre múltiplos *workers* ou instâncias do Railway. Adicione um serviço de Redis (a própria Railway tem) para o limite free de 3 gerações/dia e para evitar chamadas duplicadas à IA.
2.  **Transição de Framework (Opcional, mas Recomendada):** Para resolver o gargalo do bloqueio de I/O em IA, considere migrar para **FastAPI**. Como sua lógica já está separada em `services/`, a migração nas rotas seria simples e você ganharia suporte nativo a código assíncrono (async/await), essencial para IAs externas.

**Fase 3: UX e Regras de Negócio**
1.  **Limitação por IP/Usuário:** Atualmente, não parece haver um controle rigoroso de sessão segura além do ID que o cliente mandar. Se um usuário "esperto" trocar o `userId` enviado no payload JSON, ele zera o contador diário e usa sua API Key de graça indefinidamente. Autenticação (JWT + Auth no banco) é fundamental.
2.  **CronJobs para Geração de Planos:** Não deixe o usuário esperando a geração. Você pode rodar um "cron" na madrugada (com Celery ou mesmo GitHub Actions chamando um endpoint interno protegido) para já pré-gerar e popular o banco com as tarefas do dia de cada usuário.

### Conclusão
O código é bem limpo, estruturado, e atende bem à premissa de um MVP guiado (Zero Decision). A lógica de fallbacks garante resiliência na demonstração. A prioridade técnica #1 é plugar de verdade o banco de dados, caso contrário, nenhum estudo do usuário será retido após o próximo deploy. E prioridade de segurança #0: revogue a chave do banco enviada no prompt original e remova ela dos seus arquivos locais imediatamente.
