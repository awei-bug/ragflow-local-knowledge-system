import { IProviderModelItem } from '@/interfaces/request/llm';
import { filterModelsCatalog } from './hooks';

const models: IProviderModelItem[] = [
  {
    name: 'vendor/free-chat',
    model_types: ['chat'],
    max_tokens: 8192,
    features: [],
    is_free: true,
  },
  {
    name: 'vendor/paid-chat',
    model_types: ['chat'],
    max_tokens: 8192,
    features: [],
    is_free: false,
  },
  {
    name: 'vendor/free-embedding',
    model_types: ['embedding'],
    max_tokens: 8192,
    features: [],
    is_free: true,
  },
];

describe('filterModelsCatalog', () => {
  it('shows only free models when the free filter is enabled', () => {
    expect(
      filterModelsCatalog(models, '', null, true).map((model) => model.name),
    ).toEqual(['vendor/free-chat', 'vendor/free-embedding']);
  });

  it('composes the free filter with search and model type filters', () => {
    expect(
      filterModelsCatalog(models, 'vendor', 'chat', true).map(
        (model) => model.name,
      ),
    ).toEqual(['vendor/free-chat']);
  });

  it('shows paid and free models when the free filter is disabled', () => {
    expect(filterModelsCatalog(models, '', null, false)).toHaveLength(3);
  });
});
