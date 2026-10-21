"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { GlowInput } from "@/components/ui/glow-input";
import { Spinner } from "@/components/ui/spinner";
import { ApiError } from "@/lib/api/client";
import { useCreateDatasource } from "@/lib/queries";

export function ConnectDialog() {
  const [open, setOpen] = useState(false);
  const create = useCreateDatasource();
  const error = create.error instanceof ApiError ? create.error : null;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) create.reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus aria-hidden />
          Подключить
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            create.mutate(
              {
                name: String(form.get("name")).trim(),
                connection_url: String(form.get("connection_url")).trim(),
              },
              {
                onSuccess: (d) => {
                  setOpen(false);
                  toast.success(`«${d.name}» подключён, идёт индексация схемы`);
                },
              },
            );
          }}
        >
          <DialogHeader>
            <DialogTitle>Подключить PostgreSQL</DialogTitle>
            <DialogDescription>
              Нужна роль только для чтения: при подключении проверяются её
              права, а строка подключения хранится зашифрованной.
            </DialogDescription>
          </DialogHeader>
          <FieldGroup className="py-4">
            {error && (
              <Alert variant="destructive">
                <AlertTitle>Не удалось подключить</AlertTitle>
                <AlertDescription className="break-words">
                  {error.message}
                </AlertDescription>
              </Alert>
            )}
            <Field>
              <FieldLabel htmlFor="ds-name">Название</FieldLabel>
              <GlowInput
                id="ds-name"
                name="name"
                required
                maxLength={200}
                placeholder="Продажи"
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="ds-url">Строка подключения</FieldLabel>
              <GlowInput
                id="ds-url"
                name="connection_url"
                required
                maxLength={2000}
                autoComplete="off"
                spellCheck={false}
                placeholder="postgresql://reader:password@host:5432/db"
                className="font-mono text-xs"
              />
              <FieldDescription>
                Роль без прав INSERT, UPDATE, DELETE, CREATE и TEMP
              </FieldDescription>
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Spinner />}
              Подключить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
