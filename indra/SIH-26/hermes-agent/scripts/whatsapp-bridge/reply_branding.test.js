import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_REPLY_PREFIX, isAgentReply } from './reply_branding.js';

test('new replies use Indra branding', () => {
  assert.match(DEFAULT_REPLY_PREFIX, /Indra · Origo Labs/);
  assert.doesNotMatch(DEFAULT_REPLY_PREFIX, /Hermes/i);
  assert.ok(isAgentReply(DEFAULT_REPLY_PREFIX + 'Ready'));
});
test('old replies and custom prefixes remain protected from self-chat loops', () => {
  assert.ok(isAgentReply('⚕ *Hermes Agent*\n────────────\nReady'));
  assert.ok(isAgentReply('My assistant: Ready', 'My assistant: '));
  assert.equal(isAgentReply('A private note', ''), false);
  assert.equal(isAgentReply('Indra is my assistant'), false);
});
