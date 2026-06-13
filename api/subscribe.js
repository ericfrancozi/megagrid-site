/**
 * MEGAGRID — Newsletter via Brevo (ex-Sendinblue)
 * Vercel Serverless Function: POST /api/subscribe
 *
 * Variáveis de ambiente necessárias (Vercel → Settings → Environment Variables):
 *   BREVO_API_KEY   → sua API key do Brevo (Settings → SMTP & API → API Keys)
 *   BREVO_LIST_ID   → ID da lista de contatos (número inteiro, ex: 3)
 *
 * Fluxo:
 *   1. Recebe { email } no body
 *   2. Valida e-mail
 *   3. Chama API Brevo para criar/atualizar contato na lista
 *   4. Retorna { ok: true } ou { error }
 */

const BREVO_API = 'https://api.brevo.com/v3';

export default async function handler(req, res) {
  // Só aceita POST
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Método não permitido' });
  }

  // CORS — permite chamada do próprio domínio e localhost
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  // Lê body
  let email;
  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    email = (body && body.email || '').toString().trim().toLowerCase();
  } catch {
    return res.status(400).json({ message: 'Body inválido' });
  }

  // Valida e-mail simples
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ message: 'E-mail inválido' });
  }

  // Checagem de variáveis de ambiente
  const apiKey  = process.env.BREVO_API_KEY;
  const listId  = parseInt(process.env.BREVO_LIST_ID || '0', 10);

  if (!apiKey || !listId) {
    // Em desenvolvimento local, simula sucesso para facilitar testes
    console.warn('[subscribe] BREVO_API_KEY ou BREVO_LIST_ID não configurado — simulando sucesso');
    return res.status(200).json({ ok: true, simulated: true });
  }

  try {
    // Cria ou atualiza contato no Brevo
    const brevoRes = await fetch(`${BREVO_API}/contacts`, {
      method: 'POST',
      headers: {
        'accept':       'application/json',
        'content-type': 'application/json',
        'api-key':      apiKey,
      },
      body: JSON.stringify({
        email,
        listIds: [listId],
        updateEnabled: true, // se já existir, só adiciona à lista
        attributes: {
          SOURCE: 'megagrid-site',
          SIGNUP_DATE: new Date().toISOString().split('T')[0],
        },
      }),
    });

    // 201 = criado, 204 = já existia e foi atualizado — ambos são sucesso
    if (brevoRes.status === 201 || brevoRes.status === 204) {
      return res.status(200).json({ ok: true });
    }

    // Erro da API Brevo
    const errBody = await brevoRes.json().catch(() => ({}));
    console.error('[subscribe] Brevo error:', brevoRes.status, errBody);

    // Se o contato já existe na lista (duplicado) — ainda é "sucesso" para o usuário
    if (brevoRes.status === 400 && errBody.code === 'duplicate_parameter') {
      return res.status(200).json({ ok: true });
    }

    return res.status(500).json({ message: 'Erro ao cadastrar. Tente novamente.' });

  } catch (err) {
    console.error('[subscribe] Fetch error:', err);
    return res.status(500).json({ message: 'Erro interno. Tente novamente.' });
  }
}
