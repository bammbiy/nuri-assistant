from __future__ import annotations

import tkinter as tk
from datetime import datetime, time, timedelta
from tkinter import messagebox, ttk

from ..schedule import ScheduleStore, format_day


class ScheduleWindow(tk.Toplevel):
    """Upcoming events (today through the next 60 days), with delete."""

    def __init__(self, master: tk.Misc, store: ScheduleStore) -> None:
        super().__init__(master)
        self.title("일정")
        self.geometry("560x420")
        self.attributes("-topmost", True)
        self.store = store

        columns = ("day", "time", "title", "remind")
        self.table = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for column, label, width, anchor in (
            ("day", "날짜", 90, "center"),
            ("time", "시간", 80, "center"),
            ("title", "일정", 250, "w"),
            ("remind", "알림", 100, "center"),
        ):
            self.table.heading(column, text=label)
            self.table.column(column, width=width, anchor=anchor)
        self.table.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        bar = ttk.Frame(self, padding=(12, 0, 12, 12))
        bar.pack(fill="x")
        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var).pack(side="left")
        ttk.Button(bar, text="닫기", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="선택 삭제", command=self.delete_selected).pack(side="right", padx=6)
        ttk.Button(bar, text="새로고침", command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        self.table.delete(*self.table.get_children())
        today = datetime.combine(datetime.now().date(), time(0, 0))
        events = self.store.between(today, today + timedelta(days=61))
        for event in events:
            remind = "-" if event.remind_at is None else ("완료" if event.reminded else event.remind_at.strftime("%m/%d %H:%M"))
            self.table.insert(
                "", "end", iid=str(event.id),
                values=(format_day(event.start.date()), "하루 종일" if event.all_day else event.start.strftime("%H:%M"), event.title, remind),
            )
        self.count_var.set(f"앞으로 60일 일정 {len(events)}개" if events else "등록된 일정이 없어요. 비서에게 말로 등록해 보세요.")

    def delete_selected(self) -> None:
        selected = self.table.selection()
        if not selected:
            return
        if not messagebox.askyesno("일정 삭제", f"선택한 일정 {len(selected)}개를 삭제할까요?", parent=self):
            return
        for event_id in selected:
            self.store.delete(int(event_id))
        self.refresh()
