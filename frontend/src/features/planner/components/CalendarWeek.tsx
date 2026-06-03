import { calendarBlocks, weekDateLabels, weekDays } from "../lib/calendar";
import type { ScheduleItem } from "../types/planner";

interface CalendarWeekProps {
  weekStart: string;
  items: ScheduleItem[];
}

const hours = Array.from({ length: 16 }, (_, index) => `${String(index + 9).padStart(2, "0")}:00`);

export function CalendarWeek({ weekStart, items }: CalendarWeekProps) {
  const labels = weekDateLabels(weekStart);
  const blocks = calendarBlocks(items);

  return (
    <div className="calendar-card">
      <div className="calendar-header-grid">
        <div>시간</div>
        {labels.map((label, index) => (
          <div key={label} className={index === 0 ? "today" : ""}>
            {label}
          </div>
        ))}
      </div>
      <div className="calendar-grid">
        <div className="time-axis">
          {hours.map((hour) => (
            <span key={hour}>{hour}</span>
          ))}
        </div>
        {weekDays.map((day, dayIndex) => (
          <div className="day-lane" key={day} aria-label={`${day}요일`}>
            {blocks
              .filter((block) => block.dayIndex === dayIndex)
              .map((block) => (
                <article
                  className={`calendar-event ${block.type}`}
                  key={block.id}
                  style={{
                    top: `calc(${block.topPercent}% + 3px)`,
                    height: `calc(${block.heightPercent}% - 6px)`,
                  }}
                >
                  <strong>{block.title}</strong>
                  <span>{block.time}</span>
                </article>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}
