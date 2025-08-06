import { NextApiRequest, NextApiResponse } from 'next';
import { login } from '@/lib/auth';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { password } = req.body;
  console.log('Login attempt for password:', password ? '[PROVIDED]' : '[MISSING]');

  if (!password) {
    return res.status(400).json({ error: 'Password required' });
  }

  const loginResult = login(password, res);
  console.log('Login result:', loginResult);
  console.log('Response headers after login:', res.getHeaders());

  if (loginResult) {
    return res.status(200).json({ success: true, debug: 'Cookie should be set' });
  }

  return res.status(401).json({ error: 'Invalid password' });
}