import React, { forwardRef, useEffect, useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as PopoverPrimitive from '@radix-ui/react-popover';
import * as SelectPrimitive from '@radix-ui/react-select';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Toaster as SonnerToaster, toast } from 'sonner';
import { Check, ChevronDown, ChevronUp, X } from 'lucide-react';
import { cn } from '../lib/cn';

const buttonVariants = cva('ui-button', {
  variants: {
    variant: {
      default: 'ui-button--default',
      primary: 'ui-button--primary',
      ghost: 'ui-button--ghost',
      danger: 'ui-button--danger',
    },
    size: {
      default: 'ui-button--md',
      sm: 'ui-button--sm',
      icon: 'ui-button--icon',
    },
  },
  defaultVariants: { variant: 'default', size: 'default' },
});

type NativeButtonProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'type'>;

export interface ButtonProps extends NativeButtonProps, VariantProps<typeof buttonVariants> {
  type?: 'default' | 'primary' | 'ghost' | 'danger';
  htmlType?: 'button' | 'submit' | 'reset';
  block?: boolean;
  icon?: React.ReactNode;
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, type = 'default', variant, size, htmlType = 'button', block, icon, asChild, children, ...props },
  ref,
) {
  const Component = asChild ? Slot : 'button';
  return (
    <Component
      ref={ref}
      type={asChild ? undefined : htmlType}
      className={cn(buttonVariants({ variant: variant || type, size }), block && 'ui-button--block', className)}
      {...props}
    >
      {icon && <span className="ui-button__icon" aria-hidden="true">{icon}</span>}
      {children}
    </Component>
  );
});

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={cn('ui-input', className)} {...props} />;
});

export type SelectOption = { value: string; label: string };

export function Select({
  value,
  onChange,
  options,
  placeholder = '请选择',
  ariaLabel,
  className,
  compact = false,
}: {
  value?: string | number;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  ariaLabel?: string;
  className?: string;
  compact?: boolean;
}) {
  const current = String(value ?? '');
  const emptyValue = '__pangdun_empty__';
  return (
    <SelectPrimitive.Root value={current || emptyValue} onValueChange={(next) => onChange(next === emptyValue ? '' : next)}>
      <SelectPrimitive.Trigger className={cn('ui-select-trigger', compact && 'ui-select-trigger--compact', className)} aria-label={ariaLabel}>
        <SelectPrimitive.Value />
        <SelectPrimitive.Icon className="ui-select-chevron"><ChevronDown size={14} /></SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="ui-select-content" position="popper" sideOffset={6} collisionPadding={12}>
          <SelectPrimitive.ScrollUpButton className="ui-select-scroll"><ChevronUp size={14} /></SelectPrimitive.ScrollUpButton>
          <SelectPrimitive.Viewport className="ui-select-viewport">
            <SelectPrimitive.Item value={emptyValue} className="ui-select-item">
              <SelectPrimitive.ItemText>{placeholder}</SelectPrimitive.ItemText>
              <SelectPrimitive.ItemIndicator className="ui-select-check"><Check size={14} /></SelectPrimitive.ItemIndicator>
            </SelectPrimitive.Item>
            {options.map((option) => (
              <SelectPrimitive.Item key={option.value} value={option.value} className="ui-select-item">
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="ui-select-check"><Check size={14} /></SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
          <SelectPrimitive.ScrollDownButton className="ui-select-scroll"><ChevronDown size={14} /></SelectPrimitive.ScrollDownButton>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('ui-card', className)} {...props} />;
}

export function Tag({ className, children }: React.HTMLAttributes<HTMLSpanElement> & { color?: string }) {
  return <span className={cn('ui-tag', className)}>{children}</span>;
}

export function Title({ className, size, children }: React.HTMLAttributes<HTMLHeadingElement> & { color?: string; size?: 'large' }) {
  const Component = size === 'large' ? 'h1' : 'h2';
  return <Component className={cn('ui-title', size === 'large' && 'ui-title--large', className)}>{children}</Component>;
}

type TableColumn<T> = {
  title?: React.ReactNode;
  dataIndex?: keyof T | string;
  render?: (value: unknown, row: T, index: number) => React.ReactNode;
  width?: number;
};

export function Table<T extends Record<string, unknown>>({
  columns,
  dataSource,
  rowKey,
  scroll,
  emptyText,
}: {
  columns: TableColumn<T>[];
  dataSource: T[];
  rowKey: keyof T | string;
  scroll?: { x?: number };
  emptyText?: React.ReactNode;
}) {
  return (
    <div className="ui-table-scroll">
      <table className="ui-table" style={scroll?.x ? { minWidth: scroll.x } : undefined}>
        <colgroup>{columns.map((column, index) => <col key={index} style={column.width ? { width: column.width } : undefined} />)}</colgroup>
        <thead>
          <tr>{columns.map((column, index) => <th key={index}>{column.title}</th>)}</tr>
        </thead>
        <tbody>
          {dataSource.length ? dataSource.map((row, rowIndex) => (
            <tr key={String(row[rowKey] ?? rowIndex)}>
              {columns.map((column, columnIndex) => {
                const value = column.dataIndex ? row[column.dataIndex] : undefined;
                return <td key={columnIndex}>{column.render ? column.render(value, row, rowIndex) : (value as React.ReactNode) || '—'}</td>;
              })}
            </tr>
          )) : (
            <tr><td className="ui-table__empty" colSpan={columns.length}>{emptyText}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Dialog({
  title,
  children,
  onClose,
  onOk,
  okLabel = '保存',
  cancelLabel = '取消',
  footerStart,
  variant = 'drawer',
  okType = 'primary',
  contentClassName,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onOk?: () => void;
  okLabel?: string;
  cancelLabel?: string;
  footerStart?: React.ReactNode;
  variant?: 'drawer' | 'modal';
  okType?: 'primary' | 'danger';
  contentClassName?: string;
}) {
  return (
    <DialogPrimitive.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="drawer-layer" />
        <DialogPrimitive.Content className={cn('drawer', variant === 'modal' && 'dialog-modal', contentClassName)} aria-describedby={undefined}>
          <header className="drawer-header">
            <DialogPrimitive.Title asChild><Title>{title}</Title></DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <button className="icon-button" type="button" title="关闭" aria-label="关闭"><X size={18} /></button>
            </DialogPrimitive.Close>
          </header>
          <div className="drawer-body">{children}</div>
          <footer className="drawer-footer">
            {footerStart && <div className="drawer-footer-start">{footerStart}</div>}
            <div className="drawer-footer-end">
              <Button onClick={onClose}>{cancelLabel}</Button>
              {onOk && <Button type={okType} onClick={onOk}>{okLabel}</Button>}
            </div>
          </footer>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function Popover({
  trigger,
  children,
  open,
  onOpenChange,
  align = 'start',
  className,
}: {
  trigger: React.ReactElement;
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  align?: 'start' | 'center' | 'end';
  className?: string;
}) {
  return <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}><PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger><PopoverPrimitive.Portal><PopoverPrimitive.Content className={cn('ui-popover', className)} align={align} sideOffset={7}>{children}</PopoverPrimitive.Content></PopoverPrimitive.Portal></PopoverPrimitive.Root>;
}

type ConfirmRequest = { message: string; resolve: (value: boolean) => void };

export function confirmAction(message: string): Promise<boolean> {
  return new Promise((resolve) => window.dispatchEvent(new CustomEvent<ConfirmRequest>('pangdun-confirm', { detail: { message, resolve } })));
}

export function ConfirmHost() {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);
  useEffect(() => { const listener = (event: Event) => setRequest((event as CustomEvent<ConfirmRequest>).detail); window.addEventListener('pangdun-confirm', listener); return () => window.removeEventListener('pangdun-confirm', listener); }, []);
  if (!request) return null;
  const [firstLine, ...details] = request.message.split('\n').filter(Boolean);
  const dangerous = /永久|删除|合并/.test(request.message);
  const close = (result: boolean) => { request.resolve(result); setRequest(null); };
  return <Dialog variant="modal" title={firstLine || '确认操作'} onClose={() => close(false)} onOk={() => close(true)} okLabel={dangerous ? '确认继续' : '确认'} okType={dangerous ? 'danger' : 'primary'}><p className="confirm-message">{details.join('\n') || '请确认是否继续。'}</p></Dialog>;
}

type Notice = { message: string; description?: string };

export const Notification = {
  success: ({ message, description }: Notice) => toast.success(message, { description }),
  error: ({ message, description }: Notice) => toast.error(message, { description }),
};

export function Toaster() {
  return <SonnerToaster position="top-right" richColors closeButton />;
}
