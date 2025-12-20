import { ImgHTMLAttributes, useEffect, useRef, useState } from 'react'
import Skeleton from './Skeleton'

export interface FadeInImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  wrapperClassName?: string
}

export default function FadeInImage({
  wrapperClassName = '',
  className = '',
  loading,
  decoding,
  onLoad,
  onError,
  src,
  ...props
}: FadeInImageProps) {
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    setLoaded(false)
    setHasError(false)
  }, [src])

  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    if (img.complete && img.naturalWidth > 0) {
      setLoaded(true)
    }
  }, [src])

  return (
    <div className={`relative overflow-hidden ${wrapperClassName}`}>
      {!loaded && !hasError ? (
        <div className="absolute inset-0">
          <Skeleton variant="rectangular" animation="wave" className="w-full h-full rounded-none" />
        </div>
      ) : null}
      {hasError ? (
        <div className="absolute inset-0 bg-slate-900/5 dark:bg-white/5" />
      ) : (
        <img
          ref={imgRef}
          src={src}
          loading={loading ?? 'lazy'}
          decoding={decoding ?? 'async'}
          onLoad={(e) => {
            setLoaded(true)
            onLoad?.(e)
          }}
          onError={(e) => {
            setHasError(true)
            onError?.(e)
          }}
          className={`w-full h-full transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'} dark:brightness-90 ${className}`}
          {...props}
        />
      )}
    </div>
  )
}
