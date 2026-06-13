#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  MEGAGRID — Script de setup inicial do repositório GitHub
#  Uso: bash scripts/deploy-setup.sh SEU_USUARIO_GITHUB
# ═══════════════════════════════════════════════════════════
set -e

GITHUB_USER=${1:-""}
REPO_NAME="megagrid-site"

if [ -z "$GITHUB_USER" ]; then
  echo "❌ Informe seu usuário GitHub:"
  echo "   bash scripts/deploy-setup.sh SEU_USUARIO"
  exit 1
fi

# Vai para a raiz do projeto (pasta pai de /scripts)
cd "$(dirname "$0")/.."

echo ""
echo "🔧 Inicializando repositório Git..."
git init
git add .
git commit -m "feat: Megagrid v1 — site dinâmico com robô de dados e 4 calculadoras"
git branch -M main

echo ""
echo "🔗 Conectando ao repositório remoto..."
git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git" 2>/dev/null || \
  git remote set-url origin "https://github.com/$GITHUB_USER/$REPO_NAME.git"

echo ""
echo "📤 Enviando para GitHub..."
git push -u origin main

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ Código no ar: github.com/$GITHUB_USER/$REPO_NAME"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Próximos passos (ver DEPLOY.md):                   ║"
echo "║  1. Vercel → Add New → Import Git Repository        ║"
echo "║  2. Output Directory: site                          ║"
echo "║  3. Adicionar variáveis de ambiente (Brevo, etc.)   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
