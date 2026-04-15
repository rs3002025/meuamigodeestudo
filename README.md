# Amigo de Estudo (Flask)

MVP backend/frontend mínimo da plataforma de estudos com IA focada em **zero decisão**.

## Stack
- Python 3.11+
- Flask
- PostgreSQL (estrutura preparada + fallback em memória para dev local)
- Deploy alvo: Railway

## Estrutura
- `app.py`: bootstrap HTTP
- `routes/`: endpoints de plano, tarefas e avaliação
- `services/`: lógica de negócio (plano, tarefas, IA e mensagens)
- `prompts/`: instruções de personalidade do agente
- `public/`: interface inicial extremamente simples

## Rodar local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Endpoints principais
- `POST /api/plano/iniciar`
- `GET /api/plano/<user_id>`
- `POST /api/tarefas/gerar`
- `GET /api/tarefas/<user_id>/hoje`
- `POST /api/tarefas/<user_id>/concluir`
- `POST /api/tarefas/<user_id>/desempenho`
- `GET /api/avaliacao/<user_id>/surpresa`

## Exemplo rápido
```bash
curl -X POST http://localhost:3000/api/plano/iniciar \
  -H "content-type: application/json" \
  -d '{"userId":"u1","objetivo":"concurso INSS","tempoDisponivelMin":90,"nivel":"intermediario","modo":"concurso"}'
```
