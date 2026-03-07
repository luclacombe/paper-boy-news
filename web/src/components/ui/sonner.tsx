"use client"

import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      position="bottom-center"
      offset="40vh"
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      toastOptions={{
        classNames: {
          toast:
            "!bg-[#ede5cf] !border-[#a09080] !text-[#1a1008] !shadow-md !font-[var(--font-headline)]",
          title: "!font-[var(--font-headline)] !text-sm !font-bold",
          description: "!font-[var(--font-body)] !text-xs !text-[#6b5e50]",
          actionButton: "!bg-[#1a1008] !text-[#f0e8d0] !font-[var(--font-mono)] !text-xs",
        },
      }}
      style={
        {
          "--normal-bg": "#ede5cf",
          "--normal-text": "#1a1008",
          "--normal-border": "#a09080",
          "--border-radius": "0px",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
