/**
 * Sound manager for Nexus Bot games
 * All sounds play client-side, zero server bandwidth
 * Auto-rotates between variants for variety
 */

class SoundManager {
  constructor() {
    this.enabled = localStorage.getItem('sounds_enabled') !== 'false';
    this.volume = parseFloat(localStorage.getItem('sounds_volume') || '0.7');
    this.cache = {}; // preloaded Audio objects
    this.basePath = '/sounds/';

    // Sound variants for variety
    this.variants = {
      correct: ['trivia/correct1.mp3', 'trivia/correct2.mp3', 'trivia/correct3.mp3'],
      wrong: ['trivia/wrong1.mp3', 'trivia/wrong2.mp3'],
      victory: ['general/victory.mp3'],
      gameover: ['general/gameover.mp3'],
      levelup: ['general/levelup.mp3'],
      click: ['general/click.mp3'],
      countdown: ['general/countdown.mp3'],
      tick: ['general/tick.mp3'],
      dice: ['dice/roll1.mp3', 'dice/roll2.mp3'],
      coins: ['dice/coins.mp3'],
      jackpot: ['dice/jackpot.mp3'],
      cardflip: ['cards/flip.mp3'],
      shuffle: ['cards/shuffle.mp3'],
      deal: ['cards/deal.mp3'],
      win: ['cards/win.mp3'],
      lose: ['cards/lose.mp3'],
      move: ['strategy/move.mp3'],
      attack: ['strategy/attack.mp3'],
      build: ['strategy/build.mp3'],
      defeat: ['strategy/defeat.mp3'],
      math_correct: ['math/correct.mp3'],
      math_wrong: ['math/wrong.mp3'],
      timeup: ['math/timeup.mp3'],
      word_correct: ['word/correct.mp3'],
      word_wrong: ['word/wrong.mp3'],
      hint: ['word/hint.mp3'],
      complete: ['word/complete.mp3'],
      suspense: ['trivia/suspense.mp3'],
      final_answer: ['trivia/final_answer.mp3'],
      timeout: ['trivia/timeout.mp3'],
      daily_bonus: ['general/daily_bonus.mp3'],
    };

    this._lastUsed = {}; // track last used variant per type
  }

  /**
   * Play a sound with auto-rotation between variants
   * @param {string} type - Sound type (e.g., 'correct', 'click')
   * @returns {Promise<void>}
   */
  async play(type) {
    if (!this.enabled) return;

    const variants = this.variants[type];
    if (!variants || variants.length === 0) {
      console.warn(`[SOUNDS] Unknown sound type: ${type}`);
      return;
    }

    // Pick a variant (rotate to avoid repetition)
    let variantIndex = 0;
    if (variants.length > 1) {
      const lastUsed = this._lastUsed[type] || 0;
      variantIndex = (lastUsed + 1) % variants.length;
      this._lastUsed[type] = variantIndex;
    }

    const soundPath = this.basePath + variants[variantIndex];

    try {
      // Use cached audio or create new
      let audio = this.cache[soundPath];
      if (!audio) {
        audio = new Audio(soundPath);
        audio.preload = 'auto';
        this.cache[soundPath] = audio;
      }

      // Reset and set volume
      audio.currentTime = 0;
      audio.volume = this.volume;

      // Play with autoplay policy handling
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((error) => {
          // Autoplay blocked - ignore silently
          if (error.name === 'NotAllowedError') {
            console.debug('[SOUNDS] Autoplay blocked by browser policy');
          } else {
            console.warn('[SOUNDS] Play error:', error);
          }
        });
      }
    } catch (error) {
      console.warn('[SOUNDS] Error playing sound:', error);
    }
  }

  /**
   * Preload sounds for a game to avoid delay
   * @param {string[]} types - Array of sound types to preload
   */
  preload(types) {
    if (!this.enabled) return;

    types.forEach((type) => {
      const variants = this.variants[type];
      if (!variants) return;

      variants.forEach((variant) => {
        const path = this.basePath + variant;
        if (!this.cache[path]) {
          const audio = new Audio(path);
          audio.preload = 'auto';
          this.cache[path] = audio;
        }
      });
    });
  }

  /**
   * Toggle sounds on/off
   * @returns {boolean} New enabled state
   */
  toggle() {
    this.enabled = !this.enabled;
    localStorage.setItem('sounds_enabled', this.enabled.toString());

    // Play test sound if enabling
    if (this.enabled) {
      this.play('click');
    }

    return this.enabled;
  }

  /**
   * Set volume level
   * @param {number} v - Volume 0-1
   */
  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    localStorage.setItem('sounds_volume', this.volume.toString());

    // Update all cached audio elements
    Object.values(this.cache).forEach((audio) => {
      audio.volume = this.volume;
    });
  }

  /**
   * Get current enabled state
   * @returns {boolean}
   */
  isEnabled() {
    return this.enabled;
  }

  /**
   * Get current volume
   * @returns {number}
   */
  getVolume() {
    return this.volume;
  }

  /**
   * Create a sound toggle button element
   * @returns {HTMLElement}
   */
  createToggleButton() {
    const btn = document.createElement('button');
    btn.className = 'sound-toggle-btn';
    btn.style.cssText = `
      background: none;
      border: none;
      font-size: 20px;
      cursor: pointer;
      padding: 8px;
      border-radius: 50%;
      transition: background 0.2s;
    `;

    const updateIcon = () => {
      btn.textContent = this.enabled ? '🔊' : '🔇';
      btn.title = this.enabled ? 'Sounds On (Click to mute)' : 'Sounds Off (Click to unmute)';
    };

    updateIcon();

    btn.addEventListener('click', () => {
      this.toggle();
      updateIcon();
      btn.style.background = 'var(--bg-hover)';
      setTimeout(() => {
        btn.style.background = 'none';
      }, 200);
    });

    return btn;
  }
}

// Export singleton instance
export const sounds = new SoundManager();
export default sounds;
