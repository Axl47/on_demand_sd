import { NextApiRequest, NextApiResponse } from 'next';
import { logout } from '@/lib/auth';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  logout(res);
  return res.status(200).json({ success: true });
}