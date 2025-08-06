/**
 * Utility functions for time formatting in AST (Atlantic Standard Time)
 */

/**
 * Format a date/time string or Date object to AST timezone
 * AST is UTC-4 (no daylight saving time)
 */
export function formatToAST(date: string | Date): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  // Format to AST (Atlantic Standard Time - UTC-4)
  // Using America/Halifax as it follows AST
  return dateObj.toLocaleTimeString('en-US', {
    timeZone: 'America/Puerto_Rico', // Puerto Rico uses AST year-round
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
}

/**
 * Format a date/time with full date and time in AST
 */
export function formatDateTimeAST(date: string | Date): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  return dateObj.toLocaleString('en-US', {
    timeZone: 'America/Puerto_Rico',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
}

/**
 * Get current time in AST
 */
export function getCurrentTimeAST(): string {
  return formatToAST(new Date());
}

/**
 * Format with timezone label
 */
export function formatWithTimezone(date: string | Date): string {
  return `${formatToAST(date)} AST`;
}