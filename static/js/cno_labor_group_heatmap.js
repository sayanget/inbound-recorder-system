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

    function parseColLabel(displayLab, slotLab) {
        const raw = String(displayLab || slotLab || '').trim();
        const m = raw.match(/^(\d{1,2}\/\d{1,2})\s+(\d{1,2}:\d{2})$/);
        if (m) {
            return { date: m[1], time: m[2], full: raw };
        }
        const parts = raw.split(/\s+/);
        if (parts.length >= 2) {
            return {
                date: parts[0],
                time: parts[parts.length - 1],
                full: raw,
            };
        }
        return { date: '', time: raw, full: raw };
    }

    function buildDateGroups(cols) {
        const groups = [];
        cols.forEach(function (c, i) {
            const d = c.date || '\u00a0';
            const last = groups[groups.length - 1];
            if (!last || last.date !== d) {
                groups.push({ date: d, startIdx: i, count: 1 });
            } else {
                last.count += 1;
            }
        });
        return groups;
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

        const payPieceLab = (opts && opts.payPiece) || t.pay_piece;
        const payHourlyLab = (opts && opts.payHourly) || t.pay_hourly;
        const rowHead = (opts && opts.rowLabel) || t.row_label;
        const cols = slotLabels.map(function (slot, i) {
            return parseColLabel(colLabels[i], slot);
        });
        const dateGroups = buildDateGroups(cols);
        const colCount = slotLabels.length;

        gridEl.style.display = 'grid';
        gridEl.style.gridTemplateColumns =
            'minmax(148px, 1.9fr) repeat(' + colCount + ', minmax(34px, 1fr))';
        gridEl.style.gap = '2px 3px';
        gridEl.style.fontSize = '11px';
        gridEl.style.alignItems = 'stretch';

        const stickyCorner =
            'position:sticky;left:0;z-index:5;box-shadow:4px 0 6px -3px rgba(0,0,0,0.06);';
        const stickyRow =
            'position:sticky;left:0;z-index:2;box-shadow:4px 0 6px -3px rgba(0,0,0,0.06);';
        const hdrSticky = 'position:sticky;z-index:4;';
        const hdrDateBg = 'background:#eef2f7;';
        const hdrTimeBg = 'background:#e3f0ff;';
        const hdrCornerBg =
            'background:linear-gradient(180deg,#eef2f7 0%,#eef2f7 49%,#d8e8f8 51%,#e3f0ff 100%);';
        const hdrDateStyle = hdrDateBg + hdrSticky + 'top:0;border-radius:4px 4px 0 0;'
            + 'padding:4px 2px;text-align:center;font-weight:600;font-size:10px;'
            + 'color:#4a5568;line-height:1.2;'
            + 'border-bottom:1px solid #c5d3e0;';
        const hdrTimeStyle = hdrTimeBg + hdrSticky + 'top:22px;border-radius:0 0 4px 4px;'
            + 'padding:5px 1px;text-align:center;font-weight:600;font-size:10px;'
            + 'line-height:1.1;color:#1e3a5f;'
            + 'border-bottom:1px solid var(--border-color,#dee2e6);';

        let html = '';
        html +=
            '<div style="grid-row:1 / span 2;grid-column:1;padding:6px 8px;font-weight:600;'
            + 'display:flex;align-items:center;' + stickyCorner + 'top:0;' + hdrCornerBg + hdrSticky
            + 'border-radius:4px;border-bottom:1px solid #c5d3e0;">'
            + escapeHtml(rowHead) + '</div>';

        dateGroups.forEach(function (g) {
            html +=
                '<div style="grid-row:1;grid-column:' + (g.startIdx + 2) + ' / span ' + g.count + ';'
                + hdrDateStyle + '">' + escapeHtml(g.date) + '</div>';
        });

        cols.forEach(function (c, i) {
            html +=
                '<div style="grid-row:2;grid-column:' + (i + 2) + ';' + hdrTimeStyle
                + '" title="' + escapeAttr(c.full) + '">' + escapeHtml(c.time) + '</div>';
        });

        rows.forEach(function (r, ri) {
            const rowNum = ri + 3;
            const payLab = r.pay_type === 'hourly' ? payHourlyLab : payPieceLab;
            const rowLabel =
                (r.company || '') + ' · ' + (r.group_no || '') + ' (' + payLab + ')';
            html +=
                '<div style="grid-row:' + rowNum + ';grid-column:1;padding:6px 8px;'
                + 'display:flex;align-items:center;line-height:1.25;border-radius:4px;'
                + 'background:var(--card-bg,#fff);border:1px solid var(--border-color,#e9ecef);'
                + stickyRow + '">' + escapeHtml(rowLabel) + '</div>';
            const h = r.hourly || [];
            for (let hi = 0; hi < slotLabels.length; hi++) {
                const n = Number(h[hi]) || 0;
                const lab = cols[hi] ? cols[hi].full : (colLabels[hi] || slotLabels[hi] || '');
                const tip = rowLabel + ' · ' + lab + ': ' + n;
                html +=
                    '<div style="grid-row:' + rowNum + ';grid-column:' + (hi + 2) + ';'
                    + cellStyle(n)
                    + 'display:flex;align-items:center;justify-content:center;border-radius:4px;'
                    + 'min-height:28px;font-variant-numeric:tabular-nums;padding:2px;font-size:10px;"'
                    + ' title="' + escapeAttr(tip) + '">'
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
        parseColLabel: parseColLabel,
    };
})(typeof window !== 'undefined' ? window : globalThis);
