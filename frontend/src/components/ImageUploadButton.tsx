import { useCallback, useRef, useState, type ChangeEvent } from "react";
import { Upload } from "lucide-react";

import api from "../api/client";
import { useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";
import { Button } from "./ui";

export interface ImageUploadButtonProps {
  onUploaded: (url: string) => void;
  disabled?: boolean;
  accept?: string;
  maxSizeBytes?: number;
  buttonText?: string;
  loadingText?: string;
  successMessage?: string;
  errorMessageFallback?: string;
  uploadPath?: string;
}

export default function ImageUploadButton({
  onUploaded,
  disabled = false,
  accept = "image/*",
  maxSizeBytes = 2 * 1024 * 1024,
  buttonText = "上传",
  loadingText = "上传中...",
  successMessage = "上传成功",
  errorMessageFallback = "上传失败",
  uploadPath = "/upload/image",
}: ImageUploadButtonProps) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const uploadFile = useCallback(
    async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post(uploadPath, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const url = String((res.data as any)?.url || "").trim();
      if (!url) throw new Error("未获取到上传结果");
      return url;
    },
    [uploadPath]
  );

  const handleChange = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      e.target.value = "";
      if (!f) return;

      if (!String(f.type || "").startsWith("image/")) {
        toast.error("请选择图片文件");
        return;
      }

      if (Number(f.size || 0) > maxSizeBytes) {
        toast.error("图片大小不能超过 2MB");
        return;
      }

      if (uploading) return;
      setUploading(true);
      try {
        const url = await uploadFile(f);
        onUploaded(url);
        toast.success(successMessage);
      } catch (err) {
        toast.error(getApiErrorMessage(err, errorMessageFallback));
      } finally {
        setUploading(false);
      }
    },
    [errorMessageFallback, maxSizeBytes, onUploaded, successMessage, toast, uploadFile, uploading]
  );

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleChange}
        disabled={disabled || uploading}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        icon={Upload}
        disabled={disabled || uploading}
        isLoading={uploading}
        loadingText={loadingText}
        onClick={() => inputRef.current?.click()}
      >
        {buttonText}
      </Button>
    </div>
  );
}
