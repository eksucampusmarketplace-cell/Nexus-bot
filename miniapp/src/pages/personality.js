/**
 * miniapp/src/pages/personality.js
 * 
 * Bot personality configuration page.
 * v22: Restored missing file (alias for persona.js).
 */

import { renderPersonaPage } from './persona.js?v=1.6.0';

export async function renderPersonalityPage(container) {
  // This is an alias/wrapper around persona.js for backward compatibility
  // The page functionality is identical
  return renderPersonaPage(container);
}
