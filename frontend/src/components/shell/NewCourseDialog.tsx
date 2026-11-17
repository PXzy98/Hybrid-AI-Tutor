import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useI18n } from "@/i18n";

/** Create a course: the creator becomes its instructor. */
export default function NewCourseDialog() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: "", title: "", course_type: "general", term_label: "" });
  const types = useQuery({ queryKey: ["course-types"], queryFn: api.courseTypes, enabled: open });
  const courseType = types.data?.includes(form.course_type) ? form.course_type : types.data?.[0] ?? form.course_type;
  const create = useMutation({
    mutationFn: () => api.createCourse({ ...form, course_type: courseType }),
    onSuccess: async (course) => {
      await qc.invalidateQueries({ queryKey: ["courses"] });
      setOpen(false);
      navigate(`/courses/${course.id}`);
    },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="ghost" size="sm" className="justify-start text-muted-foreground hover:text-foreground">
          <Plus aria-hidden />{t("course.new")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t("course.new")}</DialogTitle>
            <DialogDescription>{t("course.newHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor="nc-code">{t("course.code")}</Label>
            <Input id="nc-code" autoCapitalize="off" autoCorrect="off" spellCheck={false} value={form.code} onChange={set("code")} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="nc-title">{t("course.title")}</Label>
            <Input id="nc-title" value={form.title} onChange={set("title")} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="nc-type">{t("course.type")}</Label>
            <Select id="nc-type" value={courseType} onChange={set("course_type")}>
              {(types.data ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="nc-term">{t("course.term")}</Label>
            <Input id="nc-term" value={form.term_label} onChange={set("term_label")} /></div>
          <ErrorNote error={create.error} />
          <DialogFooter><Button type="submit" loading={create.isPending}>{t("course.create")}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
