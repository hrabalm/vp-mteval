import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function isFloat(n: unknown): n is number {
    return typeof n === "number" && !Number.isNaN(n) && !Number.isInteger(n);
}
