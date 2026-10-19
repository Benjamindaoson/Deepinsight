import { memo, useState } from 'react'
import Image from 'next/image'

import { type ImageData } from '@/types/os'
import { cn } from '@/lib/utils'

function ImagePreview({ image }: { image: ImageData }) {
  const [failed, setFailed] = useState(false)
  const link = /^https?:\/\//i.test(image.url) ? image.url : undefined
  if (failed)
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-md bg-secondary/50 text-muted">
        <p className="text-primary">Image unavailable</p>
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="w-full max-w-md truncate p-2 text-center text-xs text-primary underline"
          >
            {image.url}
          </a>
        )}
      </div>
    )
  // Agent media URLs are React attributes; failed URLs never become HTML markup.
  return (
    <Image
      src={image.url}
      alt={image.revised_prompt || 'AI generated image'}
      width={768}
      height={512}
      unoptimized
      className="w-full rounded-lg"
      onError={() => setFailed(true)}
    />
  )
}

const Images = ({ images }: { images: ImageData[] }) => (
  <div
    className={cn(
      'grid max-w-xl gap-4',
      images.length > 1 ? 'grid-cols-2' : 'grid-cols-1'
    )}
  >
    {images.map((image) => (
      <div key={image.url} className="group relative">
        <ImagePreview image={image} />
      </div>
    ))}
  </div>
)

export default memo(Images)

Images.displayName = 'Images'
