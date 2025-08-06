import { NextApiRequest, NextApiResponse } from 'next';
import { createToken, verifyToken } from '@/lib/auth';

const AUTH_PASSWORD = process.env.AUTH_PASSWORD || 'comfyui123';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { password } = req.body;
  console.log('Login attempt (alt):', password ? '[PROVIDED]' : '[MISSING]');

  if (!password) {
    return res.status(400).json({ error: 'Password required' });
  }

  if (password === AUTH_PASSWORD) {
    const token = createToken();
    console.log('Generated token for alt login:', token ? '[GENERATED]' : '[FAILED]');
    
    // Return token in response instead of setting cookie
    return res.status(200).json({ 
      success: true, 
      token: token,
      debug: 'Token returned in response for client-side storage'
    });
  }

  return res.status(401).json({ error: 'Invalid password' });
}