import { Modal } from "./ui";
import PaymentMethodPicker, {
  type PaymentMethod,
  type PaymentMethodOption,
} from "./PaymentMethodPicker";

export type { PaymentMethod, PaymentMethodOption } from "./PaymentMethodPicker";

export interface PaymentMethodModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBack?: () => void;
  backLabel?: string;
  title: string;
  description?: string;
  options: PaymentMethodOption[];
  busy?: boolean;
  onSelect: (method: PaymentMethod) => void;
}

export default function PaymentMethodModal({
  isOpen,
  onClose,
  onBack,
  backLabel = "返回修改",
  title,
  description,
  options,
  busy = false,
  onSelect,
}: PaymentMethodModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        if (busy) return;
        onClose();
      }}
      title={title}
      description={description}
      size="sm"
    >
      <PaymentMethodPicker
        options={options}
        busy={busy}
        onSelect={onSelect}
        onCancel={onClose}
        onBack={onBack}
        backLabel={backLabel}
      />
    </Modal>
  );
}
