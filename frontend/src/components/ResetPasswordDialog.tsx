import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useI18n } from "@/i18n";

/** A reset ends the current password at once, so it is confirmed first (V17 W11, W26). Open while `name` is set. */
export default function ResetPasswordDialog({ name, onClose, onConfirm }: { name?: string; onClose: () => void; onConfirm: () => void }) {
  const { t } = useI18n();
  return (
    <Dialog open={name !== undefined} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.resetTitle")}</DialogTitle>
          <DialogDescription>{t("admin.resetBody", { name: name ?? "" })}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
          <Button type="button" onClick={onConfirm}>{t("admin.resetConfirm")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
