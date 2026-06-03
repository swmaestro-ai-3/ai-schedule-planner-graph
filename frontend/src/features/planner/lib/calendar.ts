import type { ScheduleItem } from "../types/planner";

export interface CalendarBlock {
  id: string;
  dayIndex: number;
  title: string;
  time: string;
  type: ScheduleItem["type"];
  topPercent: number;
  heightPercent: number;
  note: string;
}

export const weekDays = ["월", "화", "수", "목", "금", "토", "일"];

export function minutesFromTime(value: string): number {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

export function calendarBlocks(
  items: ScheduleItem[],
  dayStart = "09:00",
  dayEnd = "24:00",
): CalendarBlock[] {
  const start = minutesFromTime(dayStart);
  const end = minutesFromTime(dayEnd);
  const range = Math.max(60, end - start);

  return items.map((item) => {
    const itemStart = minutesFromTime(item.start);
    const itemEnd = minutesFromTime(item.end);
    return {
      id: item.id,
      dayIndex: item.dayIndex,
      title: item.title,
      time: `${item.start} - ${item.end}`,
      type: item.type,
      topPercent: ((itemStart - start) / range) * 100,
      heightPercent: ((itemEnd - itemStart) / range) * 100,
      note: item.note,
    };
  });
}

export function weekDateLabels(weekStart: string): string[] {
  const start = new Date(`${weekStart}T00:00:00`);
  return weekDays.map((day, offset) => {
    const target = new Date(start);
    target.setDate(start.getDate() + offset);
    const month = String(target.getMonth() + 1).padStart(2, "0");
    const date = String(target.getDate()).padStart(2, "0");
    return `${month}/${date} ${day}`;
  });
}
