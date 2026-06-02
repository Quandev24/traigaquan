/**
 * Donut Device Status Component
 * 
 * Reusable component for displaying device status donut chart
 * Used in: index.html, coop-list.html, device-list.html
 * 
 * API: GET /api/devices/status-stats
 * Response: { active: number, error: number, connecting: number, waiting: number }
 */

(function() {
    'use strict';

    const SEGMENTS = [
        { key: 'active',     label: 'Đang hoạt động',        color: '#4CAF50' },
        { key: 'error',      label: 'Lỗi',                   color: '#F44336' },
        { key: 'connecting', label: 'Đang kết nối',          color: '#FFC107' },
        { key: 'waiting',    label: 'Đang chờ được kết nối', color: '#9E9E9E' }
    ];

    const refreshIntervals = {};

    function convertToChartData(apiData) {
        return {
            'active': apiData.active || 0,
            'error': apiData.error || 0,
            'connecting': apiData.connecting || 0,
            'waiting': apiData.waiting || 0
        };
    }

    function renderDonutChart(elementId, data) {
        const container = document.getElementById(elementId);
        if (!container) {
            console.warn('Donut chart container not found:', elementId);
            return;
        }

        const segments = container.querySelectorAll('.donut-segment-coop');
        const total = SEGMENTS.reduce((sum, seg) => sum + (data[seg.key] || 0), 0);

        if (total === 0) {
            segments.forEach(segment => {
                segment.style.strokeDasharray = '0 440';
            });
            const totalEl = container.querySelector('.donut-total-coop');
            if (totalEl) totalEl.textContent = '0';
            const emptyData = {};
            SEGMENTS.forEach(s => emptyData[s.key] = 0);
            updateLegend(elementId, emptyData);
            return;
        }

        const circumference = 2 * Math.PI * 70;
        let offset = 0;

        segments.forEach(segment => {
            const segmentType = segment.getAttribute('data-segment');
            const segDef = SEGMENTS.find(s => s.key === segmentType);
            if (!segDef) return;

            const count = data[segmentType] || 0;
            const percentage = count / total;
            const dashArray = percentage * circumference;

            segment.style.strokeDasharray = `${dashArray} ${circumference}`;
            segment.style.strokeDashoffset = -offset;
            segment.setAttribute('data-count', count);
            segment.setAttribute('data-percent', Math.round(percentage * 100));
            segment.setAttribute('data-name', segDef.label);

            offset += dashArray;
        });

        const totalEl = container.querySelector('.donut-total-coop');
        if (totalEl) totalEl.textContent = total;

        updateLegend(elementId, data);
    }

    function updateLegend(elementId, data) {
        const container = document.getElementById(elementId);
        if (!container) return;

        const legendItems = container.closest('.card-body')?.querySelectorAll('.legend-item-coop');
        if (!legendItems) return;

        legendItems.forEach(item => {
            const segmentType = item.getAttribute('data-segment');
            const segDef = SEGMENTS.find(s => s.key === segmentType);
            const count = data[segmentType] || 0;
            const textEl = item.querySelector('.legend-text-coop');
            const countEl = item.querySelector('.legend-count-coop');

            if (textEl && segDef) {
                textEl.textContent = segDef.label;
            }
            if (countEl) {
                countEl.textContent = `(${count})`;
            }
        });
    }

    window.loadDeviceStatusDonut = function(elementId, refreshInterval = 30000) {
        if (refreshIntervals[elementId]) {
            clearInterval(refreshIntervals[elementId]);
        }

        const fetchAndRender = async function() {
            try {
                const response = await fetch('/api/devices/status-stats');
                if (!response.ok) throw new Error('Failed to fetch device stats');

                const apiData = await response.json();
                const chartData = convertToChartData(apiData);
                renderDonutChart(elementId, chartData);
            } catch (error) {
                console.error('Error loading device status donut:', error);
            }
        };

        fetchAndRender();

        if (refreshInterval > 0) {
            refreshIntervals[elementId] = setInterval(fetchAndRender, refreshInterval);
        }

        return function() {
            if (refreshIntervals[elementId]) {
                clearInterval(refreshIntervals[elementId]);
                delete refreshIntervals[elementId];
            }
        };
    };

    window.stopDeviceStatusDonutRefresh = function(elementId) {
        if (refreshIntervals[elementId]) {
            clearInterval(refreshIntervals[elementId]);
            delete refreshIntervals[elementId];
        }
    };

    console.log('✓ donut-device-status.js loaded');

})();