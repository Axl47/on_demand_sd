import { NextApiRequest, NextApiResponse } from 'next';
import { checkAuthFlex } from '@/lib/auth';
import axios from 'axios';

const DISPATCHER_URL = process.env.DISPATCHER_URL || 'http://localhost:8187';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  console.log('Instance API - DISPATCHER_URL:', DISPATCHER_URL);
  console.log('Instance API - Environment vars:', {
    NODE_ENV: process.env.NODE_ENV,
    DISPATCHER_URL: process.env.DISPATCHER_URL
  });
  if (!checkAuthFlex(req, res)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { action } = req.query;

  try {
    switch (action) {
      case 'status':
        const statusRes = await axios.get(`${DISPATCHER_URL}/status`);
        return res.status(200).json(statusRes.data);

      case 'start':
        if (req.method !== 'POST') {
          return res.status(405).json({ error: 'Method not allowed' });
        }
        const startRes = await axios.post(`${DISPATCHER_URL}/start`);
        return res.status(200).json(startRes.data);

      case 'stop':
        if (req.method !== 'POST') {
          return res.status(405).json({ error: 'Method not allowed' });
        }
        const stopRes = await axios.post(`${DISPATCHER_URL}/stop`);
        return res.status(200).json(stopRes.data);

      case 'keep-alive':
        if (req.method !== 'POST') {
          return res.status(405).json({ error: 'Method not allowed' });
        }
        const keepAliveRes = await axios.post(`${DISPATCHER_URL}/keep-alive`);
        return res.status(200).json(keepAliveRes.data);

      default:
        return res.status(404).json({ error: 'Unknown action' });
    }
  } catch (error: any) {
    console.error(`Instance API error for action ${action}:`, error.message);
    return res.status(500).json({ 
      error: 'Failed to communicate with dispatcher',
      details: error.message 
    });
  }
}