import { DynamicForm } from '@/components/dynamic-form';
import { Button } from '@/components/ui/button';
import Divider from '@/components/ui/divider';
import { Form } from '@/components/ui/form';
import { MainContainer } from '@/pages/dataset/dataset-setting/configuration-form-container';
import { TopTitle } from '@/pages/dataset/dataset-title';
import { IMemory } from '@/pages/memories/interface';
import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { useFetchMemoryBaseConfiguration } from '../hooks/use-memory-setting';
import {
  AdvancedSettingsForm,
  advancedSettingsFormSchema,
  defaultAdvancedSettingsForm,
} from './advanced-settings-form';
import { BasicInfo, basicInfoSchema, defaultBasicInfo } from './basic-form';
import { useUpdateMemoryConfig } from './hook';
import {
  MemoryModelForm,
  defaultMemoryModelForm,
  memoryModelFormSchema,
} from './memory-model-form';
import { MemorySettingProvider } from './memory-setting-context';

export default function MemorySetting() {
  const { t } = useTranslation();
  const MemorySettingSchema = z.object({
    id: z.string(),
    ...basicInfoSchema,
    ...memoryModelFormSchema(t),
    ...advancedSettingsFormSchema,
  });
  const form = useForm<IMemory>({
    resolver: zodResolver(MemorySettingSchema),
    defaultValues: {
      id: '',
      ...defaultBasicInfo,
      ...defaultMemoryModelForm,
      ...defaultAdvancedSettingsForm,
    } as unknown as IMemory,
  });
  const { data } = useFetchMemoryBaseConfiguration();
  const { onMemoryRenameOk, loading } = useUpdateMemoryConfig();

  useEffect(() => {
    form.reset({
      id: data?.id,
      embd_id: data?.embd_id,
      llm_id: data?.llm_id,
      name: data?.name || '',
      description: data?.description || '',
      avatar: data?.avatar || '',
      memory_size: data?.memory_size,
      memory_type: data?.memory_type,
      temperature: data?.temperature,
      system_prompt: data?.system_prompt || '',
      user_prompt: data?.user_prompt || '',
      forgetting_policy: data?.forgetting_policy || 'FIFO',
      storage_type: (data?.storage_type || 'table').toLowerCase(),
      permissions: data?.permissions || 'me',
    });
  }, [data, form]);

  const onSubmit = (values: IMemory) => {
    onMemoryRenameOk({
      ...values,
      storage_type: (values.storage_type || 'table').toLowerCase(),
    } as IMemory);
  };

  return (
    <section className="flex h-full flex-col">
      <TopTitle
        title={t('memory.config.title')}
        description={t('memory.config.titleDescription')}
      />
      <div className="flex min-h-0 flex-1 gap-6 lg:gap-14">
        <MemorySettingProvider data={data}>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="flex min-h-0 w-full max-w-3xl flex-col space-y-6"
            >
              <div className="min-h-0 flex-1 overflow-y-auto pr-1 pb-4 scrollbar-auto">
                <MainContainer className="space-y-10 text-text-secondary !space-y-10">
                  <div className="text-base font-medium text-text-primary">
                    {t('memory.config.baseInfo')}
                  </div>
                  <BasicInfo />
                  <Divider />
                  <MemoryModelForm />
                  <AdvancedSettingsForm />
                </MainContainer>
              </div>
              <div className="flex w-full max-w-3xl items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    form.reset();
                  }}
                >
                  {t('memory.config.cancel')}
                </Button>
                <DynamicForm.SavingButton
                  submitLoading={loading}
                  submitFunc={(value) => {
                    onSubmit(value as IMemory);
                  }}
                />
              </div>
            </form>
          </Form>
        </MemorySettingProvider>
      </div>
    </section>
  );
}
