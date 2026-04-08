
        window.onerror = function(msg, url, line) {
            console.error('JS Error:', msg, 'Line:', line);
            return true;
        };
        
        console.log('Dashboard script starting...');
        
        let filterHours = 0;
        let autoRunning = false;
        let currentSignalIdx = -1;
        let selectedPairs = ['XAUUSD', 'EURUSD', 'GBPUSD'];
        let lastScanTime = null;
        let allSignals = [];
        
        const ALL_PAIRS = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD'];
        
        function log(msg) { console.log('[Dashboard]', msg); }
        
        function $(id) { return document.getElementById(id); }
        
        function show(el) { if($(el)) $(el).style.display = 'block'; }
        function hide(el) { if($(el)) $(el).style.display = 'none'; }
        function setHTML(el, html) { if($(el)) $(el).innerHTML = html; }
        function setText(el, text) { if($(el)) $(el).textContent = text; }
        
        function fmt(v, d) {
            v = parseFloat(v);
            if (isNaN(v)) return d === 0 ? '0' : '0.00';
            return v.toFixed(d);
        }
        
        function api(url, method) {
            method = method || 'GET';
            log('API: ' + method + ' ' + url);
            return fetch(url + (url.includes('?') ? '&' : '?') + '_=' + Date.now(), {method: method})
                .then(function(r) {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .catch(function(err) {
                    log('API Error: ' + err.message);
                    return null;
                });
        }
        
        function refresh() {
            log('Refreshing...');
            api('/api/status?hours=' + filterHours).then(function(data) {
                if (!data) {
                    log('No data received');
                    return;
                }
                
                log('Got data: balance=' + data.balance + ', session=' + data.session.code);
                
                hide('loading');
                show('dashboard');
                
                // Status bar
                setHTML('statusBar',
                    '<div class="status-item"><span class="status-label">MT5:</span><span class="status-value ' + (data.mt5_connected ? 'green' : 'red') + '">' + (data.mt5_connected ? 'Connected' : 'Disconnected') + '</span></div>' +
                    '<div class="status-item"><span class="status-label">Balance:</span><span class="status-value">$' + fmt(data.balance, 2) + '</span></div>' +
                    '<div class="status-item"><span class="status-label">Equity:</span><span class="status-value">$' + fmt(data.equity, 2) + '</span></div>' +
                    '<div class="status-item"><span class="status-label">Floating:</span><span class="status-value ' + (data.profit >= 0 ? 'green' : 'red') + '">' + (data.profit >= 0 ? '+' : '') + '$' + fmt(data.profit, 2) + '</span></div>' +
                    '<div class="status-item"><span class="status-label">Positions:</span><span class="status-value blue">' + data.positions + '/2</span></div>'
                );
                
                // Auto button
                autoRunning = data.running || false;
                $('btnAuto').innerHTML = 'AUTO: ' + (autoRunning ? 'ON' : 'OFF');
                $('btnAuto').style.background = autoRunning ? '#238636' : '#1f6feb';
                
                // Sessions
                var sess = data.session || {};
                var sessCode = sess.code || 'OFF';
                var sessions = ['SYDNEY', 'TOKYO', 'LONDON', 'NEW_YORK', 'OVERLAP', 'SILVER_BULLET', 'OFF_HOURS'];
                var sessHTML = '';
                sessions.forEach(function(s) {
                    var cls = 'session-item';
                    if (s === sessCode) cls += ' session-active';
                    if (['LONDON', 'NEW_YORK', 'OVERLAP', 'SILVER_BULLET'].indexOf(s) >= 0) cls += ' session-good';
                    sessHTML += '<div class="' + cls + '">' + s.replace('_', ' ') + '</div>';
                });
                setHTML('sessionBar', sessHTML);
                
                setText('curSession', sess.name || sessCode);
                setText('bestPairs', (sess.best_pairs || []).join(', ') || 'None');
                $('canTrade').innerHTML = data.is_tradeable 
                    ? '<span class="green">YES</span>' 
                    : '<span class="red">NO</span>';
                
                // Pair checkboxes
                var pairHTML = '';
                ALL_PAIRS.forEach(function(p) {
                    var sel = selectedPairs.indexOf(p) >= 0;
                    pairHTML += '<label class="pair-checkbox' + (sel ? ' selected' : '') + '">' +
                        '<input type="checkbox"' + (sel ? ' checked' : '') + ' onchange="togglePair(&quot;' + p + '&quot;)">' + p +
                        '</label>';
                });
                setHTML('pairCheckboxes', pairHTML);
                
                // Stats grid
                setHTML('statsGrid',
                    '<div class="stat-box"><div class="stat-value">$' + fmt(data.balance, 2) + '</div><div class="stat-label">Balance</div></div>' +
                    '<div class="stat-box"><div class="stat-value">$' + fmt(data.equity, 2) + '</div><div class="stat-label">Equity</div></div>' +
                    '<div class="stat-box"><div class="stat-value ' + (data.profit >= 0 ? 'green' : 'red') + '">' + (data.profit >= 0 ? '+' : '') + '$' + fmt(data.profit, 2) + '</div><div class="stat-label">Floating</div></div>' +
                    '<div class="stat-box"><div class="stat-value blue">' + data.positions + '/2</div><div class="stat-label">Positions</div></div>' +
                    '<div class="stat-box"><div class="stat-value">' + fmt(data.drawdown, 1) + '%</div><div class="stat-label">Drawdown</div></div>' +
                    '<div class="stat-box"><div class="stat-value">$' + fmt(data.margin_free, 0) + '</div><div class="stat-label">Free Margin</div></div>'
                );
                
                // Market directions
                var dirs = data.market_directions || {};
                var dirHTML = '';
                Object.keys(dirs).forEach(function(sym) {
                    var d = dirs[sym] || {};
                    var trend = d.trend || 'NEUTRAL';
                    var cls = trend === 'BULLISH' ? 'bull' : trend === 'BEARISH' ? 'bear' : '';
                    dirHTML += '<div class="dir-card ' + cls + '">' +
                        '<div class="dir-symbol">' + sym + '</div>' +
                        '<div class="dir-trend">' + trend + ' | ADX: ' + fmt(d.adx, 1) + '</div>' +
                        '</div>';
                });
                setHTML('dirGrid', dirHTML || '<div class="no-data">No market data</div>');
                
                // Signals
                lastScanTime = data.last_scan;
                allSignals = data.scan_results || [];
                setText('signalCount', '(' + allSignals.length + ')');
                
                if (allSignals.length === 0) {
                    setHTML('signals', '<div class="no-data">No signals. Click SCAN NOW to find opportunities.</div>');
                } else {
                    var sigHTML = '';
                    allSignals.forEach(function(s, i) {
                        var dir = (s.direction || 'BUY').toLowerCase();
                        var blocked = !s.can_trade;
                        sigHTML += '<div class="signal-card ' + dir + '">' +
                            '<div class="signal-header">' +
                            '<span class="signal-symbol">' + (s.symbol || '?') + '</span>' +
                            '<span class="signal-badge ' + dir + '">' + (s.direction || '?') + '</span>' +
                            '</div>' +
                            '<div class="signal-details">' +
                            '<div class="signal-item"><div class="signal-label">Entry</div><div class="signal-value">' + fmt(s.entry, 5) + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">SL</div><div class="signal-value loss">' + fmt(s.sl, 5) + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">TP</div><div class="signal-value profit">' + fmt(s.tp, 5) + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">R:R</div><div class="signal-value">1:' + (s.rr_ratio || 0) + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">Risk</div><div class="signal-value">$' + fmt(s.risk_amount, 2) + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">Lot</div><div class="signal-value">' + (s.lot || 0) + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">H4</div><div class="signal-value">' + (s.h4_trend || '?') + '</div></div>' +
                            '<div class="signal-item"><div class="signal-label">RSI</div><div class="signal-value">' + fmt(s.h1_rsi, 1) + '</div></div>' +
                            '</div>' +
                            (blocked ? '<div style="background:#3d2a00;color:#d29922;padding:8px;border-radius:4px;margin:8px 0;font-size:11px;">Warning: ' + (s.trade_reason || 'Blocked') + '</div>' : '') +
                            '<div class="signal-footer">' +
                            '<span class="signal-timer" id="timer-' + i + '">Scanning...</span>' +
                            '<button class="signal-enter" onclick="showTrade(' + i + ')">' + (blocked ? 'Enter Anyway' : 'Enter') + '</button>' +
                            '</div></div>';
                    });
                    setHTML('signals', sigHTML);
                }
                
                // Positions
                var pos = data.open_positions || [];
                if (pos.length === 0) {
                    setHTML('positions', '<div class="no-data">No open positions</div>');
                } else {
                    var posHTML = '<table class="positions"><tr><th>Symbol</th><th>Type</th><th>Entry</th><th>Current</th><th>P/L</th><th></th></tr>';
                    pos.forEach(function(p) {
                        var pClass = p.profit >= 0 ? 'green' : 'red';
                        posHTML += '<tr>' +
                            '<td>' + (p.symbol || '?') + '</td>' +
                            '<td class="' + pClass + '">' + (p.type || '?') + '</td>' +
                            '<td>' + fmt(p.entry, 5) + '</td>' +
                            '<td>' + fmt(p.current, 5) + '</td>' +
                            '<td class="' + pClass + '">$' + fmt(p.profit, 2) + '</td>' +
                            '<td><button class="close-btn" onclick="closePos(' + (p.ticket || 0) + ')">X</button></td>' +
                            '</tr>';
                    });
                    setHTML('positions', posHTML + '</table>');
                }
                
                // History
                var hist = data.trade_history || [];
                if (hist.length === 0) {
                    setHTML('history', '<div class="no-data">No trades in this period</div>');
                } else {
                    var histHTML = '';
                    hist.forEach(function(h) {
                        var hClass = h.profit >= 0 ? 'green' : 'red';
                        histHTML += '<div class="history-item">' +
                            '<span class="history-time">' + (h.time || '?') + '</span>' +
                            '<span><b>' + (h.symbol || '?') + '</b></span>' +
                            '<span>' + (h.type || '?') + '</span>' +
                            '<span class="' + hClass + '">$' + fmt(h.profit, 2) + '</span>' +
                            '</div>';
                    });
                    setHTML('history', histHTML);
                }
                
                log('Refresh complete');
            });
        }
        
        function updateTimers() {
            if (!lastScanTime) return;
            var scanDate = new Date(lastScanTime);
            var now = new Date();
            var diffSec = Math.floor((now - scanDate) / 1000);
            var diffMin = Math.floor(diffSec / 60);
            var timeStr = diffMin < 1 ? diffSec + 's ago' : diffMin < 60 ? diffMin + 'm ago' : Math.floor(diffMin / 60) + 'h ago';
            
            allSignals.forEach(function(s, i) {
                var el = $('timer-' + i);
                if (el) el.textContent = timeStr;
            });
        }
        
        function togglePair(pair) {
            var idx = selectedPairs.indexOf(pair);
            if (idx >= 0) selectedPairs.splice(idx, 1);
            else selectedPairs.push(pair);
            api('/api/pairs?' + selectedPairs.map(function(p) { return 'p=' + p; }).join('&'), 'POST');
            refresh();
        }
        
        function doScan() {
            setHTML('signals', '<div class="no-data" style="color:#58a6ff;">Scanning...</div>');
            api('/api/scan', 'POST').then(function() { refresh(); });
        }
        
        function toggleAuto() {
            var url = autoRunning ? '/api/stop' : '/api/start';
            api(url, 'POST').then(function() { refresh(); });
        }
        
        function closeProfitable() {
            if (!confirm('Close all profitable positions?')) return;
            api('/api/close-profitable', 'POST').then(function() { refresh(); });
        }
        
        function closeAll() {
            if (!confirm('Close ALL positions?')) return;
            api('/api/close-all', 'POST').then(function() { refresh(); });
        }
        
        function closePos(ticket) {
            if (!confirm('Close this position?')) return;
            api('/api/close/' + ticket, 'POST').then(function() { refresh(); });
        }
        
        function showTrade(idx) {
            currentSignalIdx = idx;
            var s = allSignals[idx];
            if (!s) return;
            
            setText('modalTitle', (s.symbol || '?') + ' ' + (s.direction || '?'));
            
            if (s.can_trade) {
                hide('modalWarning');
            } else {
                show('modalWarning');
                setText('modalWarning', 'Warning: ' + (s.trade_reason || 'Blocked'));
            }
            
            setHTML('modalInfo',
                '<div class="modal-info-item"><div class="signal-label">Entry</div><div class="signal-value">' + fmt(s.entry, 5) + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">SL</div><div class="signal-value loss">' + fmt(s.sl, 5) + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">TP</div><div class="signal-value profit">' + fmt(s.tp, 5) + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">R:R</div><div class="signal-value">1:' + (s.rr_ratio || 0) + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">Risk</div><div class="signal-value">$' + fmt(s.risk_amount, 2) + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">Lot</div><div class="signal-value">' + (s.lot || 0) + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">H4</div><div class="signal-value">' + (s.h4_trend || '?') + '</div></div>' +
                '<div class="modal-info-item"><div class="signal-label">RSI</div><div class="signal-value">' + fmt(s.h1_rsi, 1) + '</div></div>'
            );
            
            $('btnConfirm').textContent = s.can_trade ? 'Enter Trade' : 'Enter Anyway';
            show('modalOverlay');
            $('modalOverlay').classList.add('show');
            $('tradeModal').classList.add('show');
        }
        
        function closeModal() {
            hide('modalOverlay');
            $('modalOverlay').classList.remove('show');
            $('tradeModal').classList.remove('show');
            currentSignalIdx = -1;
        }
        
        function confirmTrade() {
            closeModal();
            if (currentSignalIdx < 0) return;
            var s = allSignals[currentSignalIdx];
            var url = s.can_trade ? '/api/execute/' + currentSignalIdx : '/api/execute-override/' + currentSignalIdx;
            api(url, 'POST').then(function(d) {
                alert((d && d.message) || (d && d.ok ? 'Trade executed!' : 'Trade failed'));
                refresh();
            });
        }
        
        function setFilter(hours, btn) {
            document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
            if (btn) btn.classList.add('active');
            filterHours = hours;
            refresh();
        }
        
        log('Starting initial load...');
        refresh();
        setInterval(refresh, 8000);
        setInterval(updateTimers, 1000);
        log('Timers started');
    