import { forwardRef } from 'react'
import { cva } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-2xl border border-transparent text-sm font-medium transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:pointer-events-none disabled:opacity-60',
  {
    variants: {
      variant: {
        default: 'bg-cyan-500 text-slate-950 hover:bg-cyan-400',
        outline: 'border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800',
        secondary: 'bg-slate-800 text-slate-100 hover:bg-slate-700',
        ghost: 'bg-transparent text-slate-100 hover:bg-slate-900/60',
        destructive: 'bg-rose-500/10 text-rose-300 hover:bg-rose-500/20',
        link: 'bg-transparent text-cyan-400 underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 gap-2 px-4',
        sm: 'h-9 gap-2 px-3 text-sm',
        lg: 'h-12 gap-3 px-5 text-base',
        icon: 'h-10 w-10 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

const Button = forwardRef(({ className, variant, size, ...props }, ref) => (
  <button
    ref={ref}
    className={cn(buttonVariants({ variant, size }), className)}
    {...props}
  />
))

Button.displayName = 'Button'

export { Button, buttonVariants }
