export interface LoadingProps {
  size?: 'sm' | 'md' | 'lg'
  text?: string
  fullScreen?: boolean
  tone?: 'dark' | 'light'
}

export default function Loading({ size = 'md', text, fullScreen = false, tone = 'dark' }: LoadingProps) {
  const isLight = tone === 'light'
  const sizeStyles = {
    sm: 'h-6 w-6 border-2',
    md: 'h-10 w-10 border-2',
    lg: 'h-16 w-16 border-4'
  }
  
  const spinner = (
    <div className="flex flex-col items-center justify-center gap-4">
      <div
        className={`${sizeStyles[size]} rounded-full animate-spin ${
          isLight ? 'border-gray-200 border-t-emerald-600' : 'border-white/20 border-t-amber-400'
        }`}
      />
      {text && <p className={`${isLight ? 'text-gray-600' : 'text-white/60'} text-sm`}>{text}</p>}
    </div>
  )
  
  if (fullScreen) {
    return (
      <div className={`fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm ${
        isLight ? 'bg-white/70' : 'bg-[#0f0a1e]/70'
      }`}>
        {spinner}
      </div>
    )
  }
  
  return (
    <div className="flex items-center justify-center py-12">
      {spinner}
    </div>
  )
}
