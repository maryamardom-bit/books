// =============================================
// تقویم شمسی اختصاصی برای پنل ادمین
// =============================================
let customCalendars = {};

function toggleCustomCalendar(event, inputId) {
    event.stopPropagation();
    const calendarId = 'calendar-' + inputId;
    const calendar = document.getElementById(calendarId);
    
    if (!calendar) return;
    
    document.querySelectorAll('.custom-jalali-calendar').forEach(el => {
        if (el.id !== calendarId) el.style.display = 'none';
    });
    
    if (calendar.style.display === 'block') {
        calendar.style.display = 'none';
        return;
    }
    
    calendar.style.display = 'block';
    
    const input = document.getElementById(inputId);
    let currentYear = 1403;
    let currentMonth = 1;
    
    if (input && input.value) {
        const parts = input.value.split('/');
        if (parts.length >= 2) {
            currentYear = parseInt(parts[0]) || 1403;
            currentMonth = parseInt(parts[1]) || 1;
        }
    }
    
    customCalendars[inputId] = { currentYear, currentMonth };
    renderCustomCalendar(inputId);
}

function renderCustomCalendar(inputId) {
    const state = customCalendars[inputId];
    if (!state) return;
    
    const calendar = document.getElementById('calendar-' + inputId);
    if (!calendar) return;
    
    const daysInMonth = getDaysInMonth(state.currentYear, state.currentMonth);
    const firstDay = getFirstDayOfMonth(state.currentYear, state.currentMonth);
    const monthNames = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
    
    let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <button type="button" onclick="changeCustomMonth('${inputId}', -1)" style="border:none; background:#faf8f6; cursor:pointer; padding:5px 10px; border-radius:5px;">→</button>
            <div style="display:flex; gap:5px;">
                <span onclick="toggleCustomYearDropdown(event, '${inputId}')" style="cursor:pointer; font-weight:700;">${state.currentYear}</span>
                <span>/</span>
                <span onclick="toggleCustomMonthDropdown(event, '${inputId}')" style="cursor:pointer; font-weight:700;">${monthNames[state.currentMonth-1]}</span>
            </div>
            <button type="button" onclick="changeCustomMonth('${inputId}', 1)" style="border:none; background:#faf8f6; cursor:pointer; padding:5px 10px; border-radius:5px;">←</button>
        </div>
        <div id="year-dropdown-${inputId}" style="display:none;"></div>
        <div id="month-dropdown-${inputId}" style="display:none;"></div>
        <table style="width:100%; text-align:center; margin-top:5px;">
            <tr><th style="padding:5px;">ش</th><th>ی</th><th>د</th><th>س</th><th>چ</th><th>پ</th><th>ج</th></tr>
            <tr>
    `;
    
    for (let i = 0; i < firstDay; i++) html += '<td></td>';
    
    for (let day = 1; day <= daysInMonth; day++) {
        if ((firstDay + day - 1) % 7 === 0 && day > 1) html += '</tr><tr>';
        html += `<td onclick="selectCustomDate('${inputId}', ${day})" style="padding:8px; cursor:pointer; border-radius:5px;">${day}</td>`;
    }
    
    html += '</tr></table>';
    calendar.innerHTML = html;
}

function toggleCustomYearDropdown(event, inputId) {
    event.stopPropagation();
    const state = customCalendars[inputId];
    const dropdown = document.getElementById('year-dropdown-' + inputId);
    
    if (dropdown.style.display === 'block') {
        dropdown.style.display = 'none';
        return;
    }
    
    let options = '';
    for (let y = state.currentYear - 60; y <= state.currentYear + 10; y++) {
        options += `<option value="${y}" ${y === state.currentYear ? 'selected' : ''}>${y}</option>`;
    }
    dropdown.innerHTML = `<select onchange="selectCustomYear('${inputId}', this.value)" style="width:100%; padding:5px; border:1px solid #ddd; border-radius:5px;">${options}</select>`;
    dropdown.style.display = 'block';
}

function toggleCustomMonthDropdown(event, inputId) {
    event.stopPropagation();
    const monthNames = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
    const dropdown = document.getElementById('month-dropdown-' + inputId);
    
    if (dropdown.style.display === 'block') {
        dropdown.style.display = 'none';
        return;
    }
    
    let options = '';
    monthNames.forEach((name, i) => {
        options += `<option value="${i+1}">${name}</option>`;
    });
    dropdown.innerHTML = `<select onchange="selectCustomMonth('${inputId}', this.value)" style="width:100%; padding:5px; border:1px solid #ddd; border-radius:5px;">${options}</select>`;
    dropdown.style.display = 'block';
}

function selectCustomYear(inputId, year) {
    customCalendars[inputId].currentYear = parseInt(year);
    document.getElementById('year-dropdown-' + inputId).style.display = 'none';
    renderCustomCalendar(inputId);
}

function selectCustomMonth(inputId, month) {
    customCalendars[inputId].currentMonth = parseInt(month);
    document.getElementById('month-dropdown-' + inputId).style.display = 'none';
    renderCustomCalendar(inputId);
}

function changeCustomMonth(inputId, delta) {
    const state = customCalendars[inputId];
    state.currentMonth += delta;
    if (state.currentMonth < 1) {
        state.currentMonth = 12;
        state.currentYear--;
    } else if (state.currentMonth > 12) {
        state.currentMonth = 1;
        state.currentYear++;
    }
    renderCustomCalendar(inputId);
}

function selectCustomDate(inputId, day) {
    const state = customCalendars[inputId];
    const formatted = `${state.currentYear}/${String(state.currentMonth).padStart(2, '0')}/${String(day).padStart(2, '0')}`;
    document.getElementById(inputId).value = formatted;
    document.getElementById('calendar-' + inputId).style.display = 'none';
}

function getDaysInMonth(year, month) {
    const monthDays = [31,31,31,31,31,31,30,30,30,30,30,29];
    if (month === 12 && isLeapYear(year)) return 30;
    return monthDays[month - 1];
}

function isLeapYear(year) {
    return year % 33 % 4 === 1;
}

function getFirstDayOfMonth(year, month) {
    const baseYear = 1403;
    const baseDay = 6;
    let totalDays = 0;
    for (let y = baseYear; y < year; y++) totalDays += isLeapYear(y) ? 366 : 365;
    for (let m = 1; m < month; m++) totalDays += getDaysInMonth(year, m);
    return (totalDays + baseDay) % 7;
}

// بستن تقویم با کلیک خارج
document.addEventListener('click', function(e) {
    if (!e.target.closest('.custom-datetime-wrapper')) {
        document.querySelectorAll('.custom-jalali-calendar').forEach(el => el.style.display = 'none');
    }
});

// راه‌اندازی
document.addEventListener('DOMContentLoaded', function() {
    // هیچ کاری لازم نیست
});