import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** A label that starts a line or a cell: its first letter in capitals ("basic" to "Basic"). */
export const capitalize = (text: string) => text.charAt(0).toLocaleUpperCase() + text.slice(1);
