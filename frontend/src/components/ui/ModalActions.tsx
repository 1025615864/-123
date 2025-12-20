import { HTMLAttributes } from 'react'

export interface ModalActionsProps extends HTMLAttributes<HTMLDivElement> {
  reverseOnMobile?: boolean
}

export default function ModalActions({
  children,
  reverseOnMobile = true,
  className = '',
  ...props
}: ModalActionsProps) {
  const base = reverseOnMobile
    ? 'flex flex-col-reverse sm:flex-row justify-end gap-3'
    : 'flex flex-col sm:flex-row justify-end gap-3'

  return (
    <div className={`${base} ${className}`} {...props}>
      {children}
    </div>
  )
}
