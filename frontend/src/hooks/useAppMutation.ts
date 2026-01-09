import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { QueryKey, UseMutationOptions } from '@tanstack/react-query'
import { useToast } from './useToast'
import { getApiErrorMessage } from '../utils'

type UnknownError = unknown

export interface AppMutationOptions<TData, TVariables, TContext>
  extends Omit<UseMutationOptions<TData, UnknownError, TVariables, TContext>, 'mutationFn'> {
  mutationFn: (variables: TVariables) => Promise<TData>
  successMessage?: string
  errorMessageFallback?: string
  invalidateQueryKeys?: QueryKey[]
  disableErrorToast?: boolean
}

export function useAppMutation<TData = unknown, TVariables = void, TContext = unknown>(
  options: AppMutationOptions<TData, TVariables, TContext>
) {
  const toast = useToast()
  const queryClient = useQueryClient()

  const {
    mutationFn,
    successMessage,
    errorMessageFallback = '操作失败，请稍后重试',
    invalidateQueryKeys,
    disableErrorToast = false,
    onSuccess,
    onError,
    ...rest
  } = options

  const meta = {
    ...(rest as any)?.meta,
    disableGlobalErrorToast: true,
  }

  return useMutation<TData, UnknownError, TVariables, TContext>({
    ...rest,
    meta,
    mutationFn,
    onSuccess: async (data, variables, context, ...extra) => {
      await (onSuccess as any)?.(data, variables, context, ...extra)

      if (successMessage) {
        toast.success(successMessage)
      }

      if (invalidateQueryKeys && invalidateQueryKeys.length > 0) {
        await Promise.all(invalidateQueryKeys.map((key) => queryClient.invalidateQueries({ queryKey: key })))
      }
    },
    onError: async (err, variables, context, ...extra) => {
      if (!disableErrorToast) {
        toast.error(getApiErrorMessage(err, errorMessageFallback))
      }
      await (onError as any)?.(err, variables, context, ...extra)
    },
  })
}
