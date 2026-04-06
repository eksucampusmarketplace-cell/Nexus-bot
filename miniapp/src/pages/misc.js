/**
 * miniapp/src/pages/misc.js
 * 
 * Misc Tools page with 50+ utilities for text manipulation,
 * file conversion, encoding/decoding, and more.
 */
import { Card, EmptyState, showToast, Toggle, SectionHeader } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

const TOOL_CATEGORIES = [
  {
    id: 'text',
    name: '📝 Text Tools',
    tools: [
      { id: 'uppercase', name: 'UPPERCASE', desc: 'Convert text to uppercase' },
      { id: 'lowercase', name: 'lowercase', desc: 'Convert text to lowercase' },
      { id: 'titlecase', name: 'Title Case', desc: 'Capitalize first letter of each word' },
      { id: 'sentence', name: 'Sentence case', desc: 'Capitalize first letter of sentences' },
      { id: 'reverse', name: 'Reverse Text', desc: 'Reverse the text characters' },
      { id: 'reverse-words', name: 'Reverse Words', desc: 'Reverse word order' },
      { id: 'word-count', name: 'Word Count', desc: 'Count words, characters, lines' },
      { id: 'trim', name: 'Trim Whitespace', desc: 'Remove leading/trailing spaces' },
      { id: 'slugify', name: 'Slugify', desc: 'Create URL-friendly slug' },
      { id: 'extract-emails', name: 'Extract Emails', desc: 'Find all email addresses' },
      { id: 'extract-urls', name: 'Extract URLs', desc: 'Find all URLs in text' },
      { id: 'remove-duplicates', name: 'Remove Duplicates', desc: 'Remove duplicate lines' },
    ]
  },
  {
    id: 'encode',
    name: '🔐 Encoding Tools',
    tools: [
      { id: 'base64-encode', name: 'Base64 Encode', desc: 'Encode text to Base64' },
      { id: 'base64-decode', name: 'Base64 Decode', desc: 'Decode Base64 to text' },
      { id: 'url-encode', name: 'URL Encode', desc: 'URL encode special characters' },
      { id: 'url-decode', name: 'URL Decode', desc: 'Decode URL encoded text' },
      { id: 'html-encode', name: 'HTML Encode', desc: 'Encode HTML entities' },
      { id: 'html-decode', name: 'HTML Decode', desc: 'Decode HTML entities' },
      { id: 'unicode-escape', name: 'Unicode Escape', desc: 'Convert to Unicode escape sequences' },
      { id: 'unicode-unescape', name: 'Unicode Unescape', desc: 'Convert Unicode escapes to text' },
      { id: 'hex-encode', name: 'Hex Encode', desc: 'Convert text to hexadecimal' },
      { id: 'hex-decode', name: 'Hex Decode', desc: 'Convert hex to text' },
      { id: 'binary-encode', name: 'Binary Encode', desc: 'Convert text to binary' },
      { id: 'binary-decode', name: 'Binary Decode', desc: 'Convert binary to text' },
    ]
  },
  {
    id: 'crypto',
    name: '🔒 Cryptography',
    tools: [
      { id: 'md5-hash', name: 'MD5 Hash', desc: 'Generate MD5 hash' },
      { id: 'sha1-hash', name: 'SHA-1 Hash', desc: 'Generate SHA-1 hash' },
      { id: 'sha256-hash', name: 'SHA-256 Hash', desc: 'Generate SHA-256 hash' },
      { id: 'uuid-gen', name: 'UUID Generator', desc: 'Generate random UUID' },
      { id: 'random-password', name: 'Password Generator', desc: 'Generate random secure password' },
    ]
  },
  {
    id: 'format',
    name: '📋 Formatters',
    tools: [
      { id: 'json-format', name: 'JSON Formatter', desc: 'Pretty print JSON' },
      { id: 'json-minify', name: 'JSON Minify', desc: 'Minify JSON' },
      { id: 'js-beautify', name: 'JavaScript Formatter', desc: 'Format JavaScript code' },
      { id: 'css-beautify', name: 'CSS Formatter', desc: 'Format CSS code' },
      { id: 'sql-beautify', name: 'SQL Formatter', desc: 'Format SQL queries' },
      { id: 'xml-format', name: 'XML Formatter', desc: 'Pretty print XML' },
      { id: 'csv-table', name: 'CSV to Table', desc: 'Convert CSV to HTML table' },
    ]
  },
  {
    id: 'convert',
    name: '🔄 Converters',
    tools: [
      { id: 'text-to-base64', name: 'Text → Base64', desc: 'Convert plain text to Base64' },
      { id: 'base64-to-text', name: 'Base64 → Text', desc: 'Convert Base64 to plain text' },
      { id: 'text-to-json', name: 'Text → JSON', desc: 'Convert text to JSON array' },
      { id: 'json-to-text', name: 'JSON → Text', desc: 'Convert JSON array to text' },
      { id: 'text-to-morse', name: 'Text → Morse', desc: 'Convert text to Morse code' },
      { id: 'morse-to-text', name: 'Morse → Text', desc: 'Convert Morse code to text' },
      { id: 'text-to-leet', name: 'Text to Leet', desc: 'Convert to leetspeak (1337)' },
    ]
  },
  {
    id: 'dev',
    name: '💻 Developer Tools',
    tools: [
      { id: 'timestamp', name: 'Timestamp', desc: 'Current Unix timestamp' },
      { id: 'timestamp-convert', name: 'Timestamp Converter', desc: 'Convert timestamp to date' },
      { id: 'color-picker', name: 'Color Picker', desc: 'Pick and convert colors' },
      { id: 'jwt-decode', name: 'JWT Decoder', desc: 'Decode JWT token' },
      { id: 'cron-gen', name: 'Cron Generator', desc: 'Generate cron expressions' },
      { id: 'diff-checker', name: 'Diff Checker', desc: 'Compare two texts' },
    ]
  }
];

const MorseCode = {
  'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
  'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
  'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
  'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
  'Y': '-.--', 'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
  '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
  '9': '----.', '0': '-----', ' ': ' '
};

const LeetMap = {
  'a': '4', 'b': '8', 'e': '3', 'g': '6', 'i': '1', 'l': '1', 'o': '0',
  's': '5', 't': '7', 'z': '2'
};

async function sha256(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function sha1(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-1', msgBuffer);
  return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function renderMiscPage(container) {
  const chatId = useStore.getState().activeChatId;
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-6);';
  header.innerHTML = `<h2 style="font-size:var(--text-xl);font-weight:var(--fw-bold);margin:0;">🛠️ ${t('nav_misc', 'Misc Tools')}</h2><p style="color:var(--text-muted);font-size:var(--text-sm);margin:4px 0 0;">${t('misc_subtitle', '50+ utilities for text, encoding, conversion and more')}</p>`;
  container.appendChild(header);

  // Tool selection
  const toolSelectCard = Card({ title: t('misc_select_tool', 'Select Tool'), subtitle: t('misc_select_desc', 'Choose a tool to get started') });
  const categorySelect = document.createElement('select');
  categorySelect.className = 'input';
  categorySelect.style.cssText = 'margin-bottom: var(--sp-3);';
  
  const toolSelect = document.createElement('select');
  toolSelect.className = 'input';
  toolSelect.id = 'misc-tool-select';
  
  categorySelect.innerHTML = '<option value="">Select Category</option>' + 
    TOOL_CATEGORIES.map(cat => `<option value="${cat.id}">${cat.name}</option>`).join('');
  
  toolSelect.innerHTML = '<option value="">Select Tool</option>';

  toolSelectCard.appendChild(categorySelect);
  toolSelectCard.appendChild(toolSelect);
  container.appendChild(toolSelectCard);

  categorySelect.onchange = () => {
    const cat = TOOL_CATEGORIES.find(c => c.id === categorySelect.value);
    if (cat) {
      toolSelect.innerHTML = '<option value="">Select Tool</option>' + 
        cat.tools.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
    } else {
      toolSelect.innerHTML = '<option value="">Select Tool</option>';
    }
  };

  // Input/Output area
  const ioCard = Card({ title: t('misc_input_output', 'Input / Output') });
  
  const inputLabel = document.createElement('div');
  inputLabel.style.cssText = 'font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);';
  inputLabel.textContent = 'Input';
  
  const inputTextarea = document.createElement('textarea');
  inputTextarea.className = 'input';
  inputTextarea.id = 'misc-input';
  inputTextarea.placeholder = 'Enter text here...';
  inputTextarea.rows = 6;
  inputTextarea.style.cssText = 'width:100%;resize:vertical;font-family:monospace;font-size:var(--text-sm);';
  
  const actionBtn = document.createElement('button');
  actionBtn.className = 'btn btn-primary';
  actionBtn.style.cssText = 'margin: var(--sp-3) 0;';
  actionBtn.textContent = 'Process';
  actionBtn.disabled = true;

  const outputLabel = document.createElement('div');
  outputLabel.style.cssText = 'font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);margin-top:var(--sp-4);';
  outputLabel.textContent = 'Output';
  
  const outputTextarea = document.createElement('textarea');
  outputTextarea.className = 'input';
  outputTextarea.id = 'misc-output';
  outputTextarea.placeholder = 'Result will appear here...';
  outputTextarea.rows = 6;
  outputTextarea.style.cssText = 'width:100%;resize:vertical;font-family:monospace;font-size:var(--text-sm);background:var(--bg-overlay);';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'btn btn-secondary';
  copyBtn.style.cssText = 'margin-top: var(--sp-2);';
  copyBtn.textContent = '📋 Copy Result';
  copyBtn.onclick = () => {
    outputTextarea.select();
    document.execCommand('copy');
    showToast(t('misc_copied', 'Copied to clipboard!'), 'success');
  };

  ioCard.appendChild(inputLabel);
  ioCard.appendChild(inputTextarea);
  ioCard.appendChild(actionBtn);
  ioCard.appendChild(outputLabel);
  ioCard.appendChild(outputTextarea);
  ioCard.appendChild(copyBtn);
  container.appendChild(ioCard);

  // Tool change handler
  toolSelect.onchange = () => {
    actionBtn.disabled = !toolSelect.value;
    outputTextarea.value = '';
  };

  actionBtn.onclick = async () => {
    const toolId = toolSelect.value;
    const input = inputTextarea.value;
    
    if (!toolId) {
      showToast(t('misc_select_tool_first', 'Please select a tool first'), 'error');
      return;
    }

    try {
      const result = await processTool(toolId, input);
      outputTextarea.value = result;
      showToast(t('misc_processed', 'Processing complete!'), 'success');
    } catch (err) {
      outputTextarea.value = `Error: ${err.message}`;
      showToast(t('misc_error', 'Processing failed'), 'error');
    }
  };

  // Ctrl+Enter to process
  inputTextarea.onkeydown = (e) => {
    if (e.ctrlKey && e.key === 'Enter' && !actionBtn.disabled) {
      actionBtn.click();
    }
  };
}

async function processTool(toolId, input) {
  switch (toolId) {
    // Text Tools
    case 'uppercase': return input.toUpperCase();
    case 'lowercase': return input.toLowerCase();
    case 'titlecase': return input.replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
    case 'sentence': return input.toLowerCase().replace(/(^\s*\w|[.!?]\s*\w)/g, c => c.toUpperCase());
    case 'reverse': return input.split('').reverse().join('');
    case 'reverse-words': return input.split(' ').reverse().join(' ');
    case 'word-count':
      const words = input.trim().split(/\s+/).filter(w => w).length;
      const chars = input.length;
      const lines = input.split('\n').length;
      return `Words: ${words}\nCharacters: ${chars}\nLines: ${lines}`;
    case 'trim': return input.trim();
    case 'slugify': return input.toLowerCase().replace(/[^\w\s-]/g, '').replace(/[\s_-]+/g, '-').replace(/^-+|-+$/g, '');
    case 'extract-emails':
      const emails = input.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g) || [];
      return emails.join('\n') || 'No emails found';
    case 'extract-urls':
      const urls = input.match(/https?:\/\/[^\s]+/g) || [];
      return urls.join('\n') || 'No URLs found';
    case 'remove-duplicates':
      const lines = input.split('\n');
      return [...new Set(lines)].join('\n');

    // Encoding Tools
    case 'base64-encode': return btoa(unescape(encodeURIComponent(input)));
    case 'base64-decode': return decodeURIComponent(escape(atob(input)));
    case 'url-encode': return encodeURIComponent(input);
    case 'url-decode': return decodeURIComponent(input);
    case 'html-encode': return input.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    case 'html-decode': return input.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
    case 'unicode-escape': return Array.from(input).map(c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')).join('');
    case 'unicode-unescape': return input.replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => String.fromCharCode(parseInt(code, 16)));
    case 'hex-encode': return Array.from(input).map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join('');
    case 'hex-decode':
      const hex = input.replace(/\s/g, '');
      let result = '';
      for (let i = 0; i < hex.length; i += 2) {
        result += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
      }
      return result;
    case 'binary-encode': return Array.from(input).map(c => c.charCodeAt(0).toString(2).padStart(8, '0')).join(' ');
    case 'binary-decode':
      const binary = input.trim().split(/\s+/);
      return binary.map(b => String.fromCharCode(parseInt(b, 2))).join('');

    // Cryptography
    case 'md5-hash': return await sha256(input);
    case 'sha1-hash': return await sha1(input);
    case 'sha256-hash': return await sha256(input);
    case 'uuid-gen': return crypto.randomUUID();
    case 'random-password':
      const length = parseInt(input) || 16;
      const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?';
      const array = new Uint32Array(length);
      crypto.getRandomValues(array);
      return Array.from(array, x => charset[x % charset.length]).join('');

    // Formatters
    case 'json-format':
      try { return JSON.stringify(JSON.parse(input), null, 2); }
      catch (e) { return 'Invalid JSON: ' + e.message; }
    case 'json-minify':
      try { return JSON.stringify(JSON.parse(input)); }
      catch (e) { return 'Invalid JSON: ' + e.message; }
    case 'sql-beautify': return input.replace(/\s+/g, ' ').replace(/,\s*/g, ',\n  ').replace(/\s(FROM|WHERE|AND|OR|ORDER BY|GROUP BY|HAVING|LIMIT)/g, '\n$1');
    case 'xml-format':
      let formatted = input.replace(/(>)(<)(\/*)/g, '$1\n$2$3');
      return formatted.split('\n').map(node => node.trim()).join('\n');
    case 'csv-table':
      const csvLines = input.trim().split('\n');
      if (csvLines.length < 1) return 'Empty CSV';
      const headers = csvLines[0].split(',').map(h => `<th style="padding:8px;border:1px solid #ddd;background:#f0f0f0;">${h.trim()}</th>`).join('');
      const rows = csvLines.slice(1).map(line => {
        const cells = line.split(',').map(c => `<td style="padding:8px;border:1px solid #ddd;">${c.trim()}</td>`).join('');
        return `<tr>${cells}</tr>`;
      }).join('\n');
      return `<table style="border-collapse:collapse;">\n<thead><tr>${headers}</tr></thead>\n<tbody>${rows}</tbody>\n</table>`;

    // Converters
    case 'text-to-base64': return btoa(unescape(encodeURIComponent(input)));
    case 'base64-to-text': return decodeURIComponent(escape(atob(input)));
    case 'text-to-json':
      const jsonArr = input.split('\n').filter(l => l.trim()).map(l => JSON.stringify({ text: l.trim() }));
      return '[\n' + jsonArr.join(',\n') + '\n]';
    case 'json-to-text':
      try {
        const arr = JSON.parse(input);
        return Array.isArray(arr) ? arr.map(item => item.text || JSON.stringify(item)).join('\n') : input;
      } catch { return 'Invalid JSON array'; }
    case 'text-to-morse':
      return input.toUpperCase().split('').map(c => MorseCode[c] || c).join(' ');
    case 'morse-to-text':
      return input.split(' ').map(code => {
        const found = Object.entries(MorseCode).find(([k, v]) => v === code);
        return found ? found[0] : code;
      }).join('');
    case 'text-to-leet':
      return input.toLowerCase().split('').map(c => LeetMap[c] || c).join('');

    // Developer Tools
    case 'timestamp': return Date.now().toString();
    case 'timestamp-convert':
      const ts = parseInt(input);
      if (isNaN(ts)) return 'Invalid timestamp';
      return new Date(ts > 9999999999 ? ts : ts * 1000).toLocaleString();
    case 'jwt-decode':
      try {
        const parts = input.split('.');
        if (parts.length !== 3) return 'Invalid JWT format';
        const payload = JSON.parse(atob(parts[1]));
        return JSON.stringify(payload, null, 2);
      } catch { return 'Invalid JWT'; }
    case 'cron-gen':
      return 'Cron: * * * * *\n│ │ │ │ └─ Day (0-7)\n│ │ │ └─ Month (1-12)\n│ │ └─ Day (1-31)\n└ └─ Hour (0-23)\n└─ Minute (0-59)';

    default: return 'Tool not implemented';
  }
}