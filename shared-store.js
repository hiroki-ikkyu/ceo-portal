/**
 * SharedStore - アプリ間データ共有ライブラリ
 * 
 * 使い方:
 *   <script src="https://hiroki-ikkyu.github.io/ceo-portal/shared-store.js"></script>
 *   
 *   // データを書き込む（各アプリ側）
 *   SharedStore.expense.logDay({ date: '2026-03-29', spent: 2400, budget: 3000 });
 *   SharedStore.study.logSession({ date: '2026-03-29', minutes: 45, subject: 'FAR' });
 *   SharedStore.routine.logDay({ date: '2026-03-29', completed: 4, total: 6 });
 *
 *   // データを読み取る（ダッシュボード側）
 *   const today = SharedStore.getTodaySummary();
 *   // → { expense: { spent, budget, remaining }, study: { minutes, subject }, routine: { completed, total, rate } }
 *
 *   // 週間データ
 *   const week = SharedStore.getWeekSummary();
 *
 * 同一ドメイン (hiroki-ikkyu.github.io) 上の全アプリからアクセス可能。
 */

(function(global) {
  'use strict';

  const PREFIX = 'shared:';
  const VERSION = '1.0.0';

  // ─── Utility ───
  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function getDateKey(domain, date) {
    return `${PREFIX}${domain}:${date}`;
  }

  function safeGet(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      console.warn('[SharedStore] parse error:', key, e);
      return null;
    }
  }

  function safeSet(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      // 他のタブ/アプリに通知（同一ドメインなのでstorageイベントが発火）
      return true;
    } catch (e) {
      console.warn('[SharedStore] write error:', key, e);
      return false;
    }
  }

  function getDaysArray(n) {
    const days = [];
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push(d.toISOString().slice(0, 10));
    }
    return days;
  }

  // ─── Expense Module ───
  const expense = {
    /**
     * 1日の支出を記録
     * @param {Object} data - { date, spent, budget, items? }
     */
    logDay(data) {
      const date = data.date || today();
      const key = getDateKey('expense', date);
      const existing = safeGet(key) || {};
      safeSet(key, {
        ...existing,
        spent: data.spent ?? existing.spent ?? 0,
        budget: data.budget ?? existing.budget ?? 3000,
        items: data.items ?? existing.items ?? [],
        updatedAt: new Date().toISOString()
      });
    },

    getDay(date) {
      return safeGet(getDateKey('expense', date || today()));
    }
  };

  // ─── Study Module ───
  const study = {
    /**
     * 勉強セッションを記録
     * @param {Object} data - { date, minutes, subject }
     */
    logSession(data) {
      const date = data.date || today();
      const key = getDateKey('study', date);
      const existing = safeGet(key) || { sessions: [], totalMinutes: 0 };
      
      const session = {
        minutes: data.minutes || 0,
        subject: data.subject || '',
        loggedAt: new Date().toISOString()
      };

      existing.sessions.push(session);
      existing.totalMinutes = existing.sessions.reduce((s, x) => s + x.minutes, 0);
      existing.updatedAt = new Date().toISOString();
      
      safeSet(key, existing);
    },

    getDay(date) {
      return safeGet(getDateKey('study', date || today()));
    }
  };

  // ─── Routine Module ───
  const routine = {
    /**
     * ルーティン達成を記録
     * @param {Object} data - { date, completed, total, items? }
     */
    logDay(data) {
      const date = data.date || today();
      const key = getDateKey('routine', date);
      const existing = safeGet(key) || {};
      safeSet(key, {
        ...existing,
        completed: data.completed ?? existing.completed ?? 0,
        total: data.total ?? existing.total ?? 0,
        items: data.items ?? existing.items ?? [],
        updatedAt: new Date().toISOString()
      });
    },

    getDay(date) {
      return safeGet(getDateKey('routine', date || today()));
    }
  };

  // ─── Aggregation ───
  function getTodaySummary() {
    const d = today();
    const exp = expense.getDay(d);
    const stu = study.getDay(d);
    const rtn = routine.getDay(d);

    return {
      date: d,
      expense: exp ? {
        spent: exp.spent,
        budget: exp.budget,
        remaining: exp.budget - exp.spent,
        withinBudget: exp.spent <= exp.budget
      } : null,
      study: stu ? {
        minutes: stu.totalMinutes,
        sessions: stu.sessions.length,
        lastSubject: stu.sessions.length > 0
          ? stu.sessions[stu.sessions.length - 1].subject
          : null
      } : null,
      routine: rtn ? {
        completed: rtn.completed,
        total: rtn.total,
        rate: rtn.total > 0 ? Math.round((rtn.completed / rtn.total) * 100) : 0
      } : null
    };
  }

  function getWeekSummary() {
    const days = getDaysArray(7);
    return days.map(d => ({
      date: d,
      expense: expense.getDay(d),
      study: study.getDay(d),
      routine: routine.getDay(d)
    }));
  }

  /**
   * ゲーミフィケーション: 全アプリの達成スコアを算出
   * - 予算内: +1 point
   * - 勉強30分以上: +1 point
   * - ルーティン80%以上: +1 point
   * → 最大3点/日
   */
  function getTodayScore() {
    const s = getTodaySummary();
    let score = 0;
    let maxScore = 0;
    const details = [];

    if (s.expense) {
      maxScore++;
      if (s.expense.withinBudget) {
        score++;
        details.push('予算内 ✓');
      } else {
        details.push('予算超過');
      }
    }

    if (s.study) {
      maxScore++;
      if (s.study.minutes >= 30) {
        score++;
        details.push(`勉強${s.study.minutes}分 ✓`);
      } else {
        details.push(`勉強${s.study.minutes}分`);
      }
    }

    if (s.routine) {
      maxScore++;
      if (s.routine.rate >= 80) {
        score++;
        details.push(`ルーティン${s.routine.rate}% ✓`);
      } else {
        details.push(`ルーティン${s.routine.rate}%`);
      }
    }

    return { score, maxScore, details };
  }

  // ─── Export ───
  global.SharedStore = {
    version: VERSION,
    expense,
    study,
    routine,
    getTodaySummary,
    getWeekSummary,
    getTodayScore,
    // Utils
    _utils: { today, safeGet, safeSet, getDateKey, getDaysArray, PREFIX }
  };

})(typeof window !== 'undefined' ? window : this);
