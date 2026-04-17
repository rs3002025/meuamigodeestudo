# Amigo de Estudo (Flask)

MVP backend/frontend da plataforma de estudos com IA focada em **zero decisão**.

## Stack
- Python 3.11+
- Flask
- PostgreSQL (estrutura preparada + fallback em memória para dev local)
- Deploy alvo: Railway

## Estrutura
- `app.py`: bootstrap HTTP
- `routes/`: endpoints de onboarding, plano, tarefas e avaliação
- `services/`: lógica de negócio (onboarding, plano, tarefas, IA e mensagens)
- `prompts/`: instruções de personalidade do agente
- `public/`: onboarding conversacional + visão inicial de tarefas

## Rodar local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Fluxo de onboarding inteligente (2–3 etapas)
1. Pergunta intenção: "o que tu quer estudar?"
2. Backend detecta tipo: `concurso`, `escola` ou `outro`
3. Coleta mínima obrigatória:
   - concurso: pergunta se tem edital e exige matérias principais quando houver conteúdo
   - escola/outro: exige temas; se usuário insistir sem conteúdo, permite modo genérico para teste
4. Ao finalizar onboarding, já gera plano + tarefas do dia

## Endpoints principais
- `POST /api/onboarding/detectar-tipo`
- `POST /api/onboarding/finalizar`
- `POST /api/plano/iniciar`
- `GET /api/plano/<user_id>`
- `POST /api/tarefas/gerar`
- `GET /api/tarefas/<user_id>/hoje`
- `POST /api/tarefas/<user_id>/concluir`
- `POST /api/tarefas/<user_id>/desempenho`
- `GET /api/avaliacao/<user_id>/surpresa`

## Comportamentos ativos
- Streak de estudo (`dias_consecutivos`) e ausência (`dias_sem_estudar`)
- Bloqueio de conclusão fora de ordem
- Feedback imediato ao concluir tarefa
- Mensagens adaptadas por ausência, pendências e desempenho
- Avaliação invisível aleatória (20%) sem repetir conteúdo recente
