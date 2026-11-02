import { expect, it } from 'vitest';
import { artifactOpenMessage } from './artifact-errors';

it('explains missing and ambiguous files without exposing raw server details', () => {
  expect(artifactOpenMessage(new Error('404: private/path'))).toContain('may not have been created');
  expect(artifactOpenMessage(new Error('409: private/path'))).toContain('More than one file');
  expect(artifactOpenMessage(new Error('403: private/path'))).toContain('current workspace');
  expect(artifactOpenMessage(new Error('500: private/path'))).not.toContain('private/path');
});
