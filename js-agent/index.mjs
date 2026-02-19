import { Agent, run, tool } from '@openai/agents';
import { z } from 'zod';

const timeNowTool = tool({
  name: 'time_now',
  description: 'Return current UTC time in ISO8601 format',
  parameters: z.object({}),
  execute: async () => new Date().toISOString(),
});

const echoTool = tool({
  name: 'echo',
  description: 'Return the same input text',
  parameters: z.object({ text: z.string() }),
  execute: async ({ text }) => text,
});

const agent = new Agent({
  name: 'assistant',
  instructions: 'You are a reliable Chinese assistant. Use tools when needed.',
  tools: [timeNowTool, echoTool],
});

async function main() {
  const input = process.argv.slice(2).join(' ') || '现在几点？';
  const result = await run(agent, input, { maxTurns: 10 });
  console.log(result.finalOutput);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
