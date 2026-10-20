import express from 'express';
import { createMeeClient } from '@biconomy/sdk';

const app = express();
app.use(express.json());

app.post('/relay/execute', async (req, res) => {
  try {
    const { targetAddress, callData, userOpAuthorization } = req.body;

    // 1. Initialize Biconomy's Execution Node Client
    const meeClient = await createMeeClient();

    // 2. Route the transaction frame using the UserOp signature from the client
    const { hash } = await meeClient.execute({
      authorization: userOpAuthorization, // The EIP-7702 signed authority from the frontend
      delegate: true,
      instructions: [
        {
          chainId: 5042002, // Arc Testnet Chain ID (or 84532 for Base Sepolia)
          calls: [{ to: targetAddress, data: callData }],
        },
      ],
    });

    return res.json({ success: true, txHash: hash });
  } catch (error) {
    return res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(3000, () => console.log('Biconomy Relay running on port 3000'));