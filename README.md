# Amigo de Estudo (Flask)

MVP backend/frontend da plataforma de estudos com IA focada em **zero decisão**.

## O que já está funcional
- Onboarding guiado em até 3 etapas
- Exigência de conteúdo mínimo para plano útil
- Plano inicial com matérias do usuário
- Tarefas diárias com conteúdo real (explicação + exemplo + 2 exercícios)
- Mensagem curta do Amigo de Estudo citando a matéria do dia
- Conclusão sequencial (não pode pular tarefa)

## Stack
- Python 3.11+
- Flask
- PostgreSQL (estrutura preparada + fallback em memória para dev local)

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

## IA e otimização
- Cache de conteúdo por `user + matéria + tema`
- Limite free: 3 gerações de conteúdo por dia
- Se não houver chave de IA ou houver erro de rede, usa fallback local sem quebrar o fluxo

## Rodar local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
