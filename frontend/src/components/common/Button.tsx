import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;

export function PrimaryButton({ className = "", ...props }: ButtonProps) {
  return <button className={`btn btn-primary ${className}`.trim()} {...props} />;
}

export function SecondaryButton({ className = "", ...props }: ButtonProps) {
  return <button className={`btn btn-secondary ${className}`.trim()} {...props} />;
}
