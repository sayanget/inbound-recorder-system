/**
 * CNO 小组 × 小时产能热力图渲染（statistics 与分享页共用）
 */
(function (global) {
    'use strict';

    const I18N = {
        zh: {
            pay_piece: '计件',
            pay_hourly: '计时',
            row_label: '小组',
            empty: '暂无小组分时数据',
        },
        en: {
            pay_piece: 'Piece rate',
            pay_hourly: 'Hourly',
            row_label: 'Group',
            empty: 'No group hourly data',
        },
        es: {
            pay_piece: 'Pieza',
            pay_hourly: 'Hora',
            row_label: 'Grupo',
            empty: 'Sin datos por grupo/hora',
        },
    };

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function escapeAttr(s) {
        return escapeHtml(s).replace(/\n/g, ' ');
    }

    function fmtInt(n) {
        const v = Number(n) || 0;
        return v.toLocaleString('en-US');
    }

    function pickLang(lang) {
        if (lang && I18N[lang]) return I18N[lang];
        const nav = (navigator.language || 'zh').toLowerCase();
        if (nav.startsWith('es')) return I18N.es;
        if (nav.startsWith('en')) return I18N.en;
        return I18N.zh;
    }

    /**
     * @param {HTMLElement} gridEl
     * @param {object} matrix - group_hourly_matrix 或 API 根对象
     * @param {{ lang?: string }} opts
     * @returns {boolean} 是否有数据
     */
    function renderHeatmap(gridEl, matrix, opts) {
        if (!gridEl) return false;
        const t = pickLang(opts && opts.lang);
        const mx = (matrix && matrix.rows) ? matrix : (matrix && matrix.group_hourly_matrix) || matrix || {};
        const slotLabels = mx.labels || [];
        const colLabels = mx.display_labels || slotLabels;
        const rows = mx.rows || [];

        if (!rows.length || !slotLabels.length) {
            gridEl.innerHTML =
                '<div style="padding:12px;color:#856404;background:#fff8e1;border-radius:6px;line-height:1.5;">'
                + escapeHtml(t.empty) + '</div>';
            gridEl.style.display = 'block';
            return false;
        }

        let vmax = 0;
        rows.forEach(function (r) {
            const h = r.hourly || [];
            for (let i = 0; i < slotLabels.length; i++) {
                const n = Number(h[i]) || 0;
                if (n > vmax) vmax = n;
            }
        });
        if (vmax <= 0) vmax = 1;

        function cellStyle(n) {
            const v = Number(n) || 0;
            if (v <= 0) {
                return 'background:var(--table-stripe,#f1f3f5);color:#adb5bd;';
            }
            const ratio = Math.min(1, Math.pow(v / vmax, 0.5));
            const L = Math.round(94 - ratio * 48);
            const S = Math.round(35 + ratio * 50);
            const textColor = ratio > 0.55 ? '#fff' : '#1a1a1a';
            return 'background:hsl(217,' + S + '%,' + L + '%);color:' + textColor + ';font-weight:600;';
        }

        const payPieceLab = t.pay_piece;
        const payHourlyLab = t.pay_hourly;
        const rowHead = t.row_label;

        gridEl.style.display = 'grid';
        gridEl.style.gridTemplateColumns =
            'minmax(140px, 1.7fr) repeat(' + slotLabels.length + ', minmax(36px, 1fr))';
        gridEl.style.gap = '3px';
        gridEl.style.fontSize = '10px';
        gridEl.style.alignItems = 'stretch';

        const stickyCorner =
            'position:sticky;left:0;z-index:3;box-shadow:4px 0 6px -3px rgba(0,0,0,0.06);';
        const stickyRow =
            'position:sticky;left:0;z-index:2;box-shadow:4px 0 6px -3px rgba(0,0,0,0.06);';

        let html = '';
        html +=
            '<div style="padding:6px 8px;font-weight:600;border-radius:4px;background:var(--table-stripe,#f8f9fa);display:flex;align-items:center;'
            + stickyCorner + '">' + escapeHtml(rowHead) + '</div>';
        colLabels.forEach(function (lab) {
            html +=
                '<div style="padding:6px 2px;text-align:center;font-weight:600;line-height:1.15;border-radius:4px;background:var(--table-stripe,#f8f9fa);white-space:nowrap;">'
                + escapeHtml(lab) + '</div>';
        });

        rows.forEach(function (r) {
            const payLab = r.pay_type === 'hourly' ? payHourlyLab : payPieceLab;
            const rowLabel =
                (r.company || '') + ' · ' + (r.group_no || '') + ' (' + payLab + ')';
            html +=
                '<div style="padding:6px 8px;display:flex;align-items:center;line-height:1.25;border-radius:4px;background:var(--card-bg,#fff);border:1px solid var(--border-color,#e9ecef);'
                + stickyRow + '">' + escapeHtml(rowLabel) + '</div>';
            const h = r.hourly || [];
            for (let hi = 0; hi < slotLabels.length; hi++) {
                const n = Number(h[hi]) || 0;
                const lab = colLabels[hi] || slotLabels[hi] || '';
                const tip = rowLabel + ' · ' + lab + ': ' + n;
                html +=
                    '<div title="' + escapeAttr(tip) + '" style="' + cellStyle(n)
                    + 'display:flex;align-items:center;justify-content:center;border-radius:4px;min-height:30px;font-variant-numeric:tabular-nums;padding:2px;">'
                    + (n > 0 ? fmtInt(n) : '') + '</div>';
            }
        });
        gridEl.innerHTML = html;
        return true;
    }

    global.CnoLaborGroupHeatmap = {
        render: renderHeatmap,
        escapeHtml: escapeHtml,
        fmtInt: fmtInt,
        pickLang: pickLang,
    };
})(typeof window !== 'undefined' ? window : globalThis);
