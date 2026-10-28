import { useQuery, useSuspenseQuery, useMutation } from "@tanstack/react-query";
import type { UseQueryOptions, UseSuspenseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
export class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;
    constructor(status: number, statusText: string, body: unknown){
        super(`HTTP ${status}: ${statusText}`);
        this.name = "ApiError";
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}
export interface ComplexValue {
    display?: string | null;
    primary?: boolean | null;
    ref?: string | null;
    type?: string | null;
    value?: string | null;
}
export interface DuplicateCheckIn {
    description?: string;
    draft_id?: string | null;
    title?: string;
}
export interface DuplicateCheckOut {
    cached: boolean;
    elapsed_ms: number;
    matches: DuplicateMatch[];
}
export interface DuplicateMatch {
    band: "likely_duplicate" | "related" | "none";
    business_unit: string | null;
    key: string;
    kind: string;
    owner: string | null;
    score: number;
    status: string | null;
    title: string;
}
export interface FormConfigOut {
    categories: string[];
    duplicate_check: Record<string, number>;
    fields: FormFieldOut[];
    organization_label: string;
    thresholds: Record<string, number>;
}
export interface FormFieldOut {
    display_order: number;
    field_name: string;
    label: string;
    options?: string[] | null;
    required: boolean;
    type: string;
}
export interface GenieAskIn {
    conversation_id?: string | null;
    question: string;
}
export interface GenieAskOut {
    answer: string;
    columns?: string[];
    conversation_id: string;
    rows?: string[][];
    sql?: string | null;
}
export interface GenieConfigOut {
    configured: boolean;
    questions: string[];
    runs_as?: "user";
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface MatchDetailOut {
    business_unit: string | null;
    category: string | null;
    description: string | null;
    est_value_usd: number | null;
    key: string;
    kind: string;
    owner: string | null;
    status: string | null;
    title: string;
    updated_at: string | null;
}
export interface Name {
    family_name?: string | null;
    given_name?: string | null;
}
export interface PortfolioOut {
    duplicate_rate: number;
    genie_url: string | null;
    open_backlog_value: number;
    request_count: number;
    total_est_value: number;
}
export interface RequestIn {
    dup_check_failed?: boolean;
    dup_score?: number | null;
    fields: Record<string, unknown>;
    join_existing?: string | null;
    submission_id?: string | null;
    submit_anyway_reason?: string | null;
}
export interface RequestOut {
    business_unit: string | null;
    category: string | null;
    category_confidence: number | null;
    classify_ms?: number | null;
    dup_check_failed: boolean;
    dup_score: number | null;
    duplicate_of: string | null;
    est_value_usd: number | null;
    request_id: string;
    requester_email: string;
    status: string;
    submit_anyway_reason: string | null;
    submitted_at: string | null;
    title: string;
}
export interface ReviewIn {
    action: "approve" | "merge" | "reject";
    merged_into?: string | null;
    reason?: string | null;
}
export interface ReviewItemOut {
    business_unit: string | null;
    category: string | null;
    category_confidence: number | null;
    classify_ms?: number | null;
    description: string;
    dup_check_failed: boolean;
    dup_score: number | null;
    duplicate_of: string | null;
    est_value_usd: number | null;
    request_id: string;
    requester_email: string;
    status: string;
    submit_anyway_reason: string | null;
    submitted_at: string | null;
    title: string;
    top_match?: DuplicateMatch | null;
}
export interface ReviewOut {
    action: string;
    decision_id: string;
    request_id: string;
    status: string;
}
export interface User {
    active?: boolean | null;
    display_name?: string | null;
    emails?: ComplexValue[] | null;
    entitlements?: ComplexValue[] | null;
    external_id?: string | null;
    groups?: ComplexValue[] | null;
    id?: string | null;
    name?: Name | null;
    roles?: ComplexValue[] | null;
    schemas?: UserSchema[] | null;
    user_name?: string | null;
}
export const UserSchema = {
    "urn:ietf:params:scim:schemas:core:2.0:User": "urn:ietf:params:scim:schemas:core:2.0:User",
    "urn:ietf:params:scim:schemas:extension:workspace:2.0:User": "urn:ietf:params:scim:schemas:extension:workspace:2.0:User"
} as const;
export type UserSchema = typeof UserSchema[keyof typeof UserSchema];
export interface ValidationError {
    ctx?: Record<string, unknown>;
    input?: unknown;
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface CurrentUserParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const currentUser = async (params?: CurrentUserParams, options?: RequestInit): Promise<{
    data: User;
}> =>{
    const res = await fetch("/api/current-user", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const currentUserKey = (params?: CurrentUserParams)=>{
    return [
        "/api/current-user",
        params
    ] as const;
};
export function useCurrentUser<TData = {
    data: User;
}>(options?: {
    params?: CurrentUserParams;
    query?: Omit<UseQueryOptions<{
        data: User;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: currentUserKey(options?.params),
        queryFn: ()=>currentUser(options?.params),
        ...options?.query
    });
}
export function useCurrentUserSuspense<TData = {
    data: User;
}>(options?: {
    params?: CurrentUserParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: User;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: currentUserKey(options?.params),
        queryFn: ()=>currentUser(options?.params),
        ...options?.query
    });
}
export const formConfig = async (options?: RequestInit): Promise<{
    data: FormConfigOut;
}> =>{
    const res = await fetch("/api/form-config", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const formConfigKey = ()=>{
    return [
        "/api/form-config"
    ] as const;
};
export function useFormConfig<TData = {
    data: FormConfigOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: FormConfigOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: formConfigKey(),
        queryFn: ()=>formConfig(),
        ...options?.query
    });
}
export function useFormConfigSuspense<TData = {
    data: FormConfigOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: FormConfigOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: formConfigKey(),
        queryFn: ()=>formConfig(),
        ...options?.query
    });
}
export interface AskGenieParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const askGenie = async (data: GenieAskIn, params?: AskGenieParams, options?: RequestInit): Promise<{
    data: GenieAskOut;
}> =>{
    const res = await fetch("/api/genie/ask", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useAskGenie(options?: {
    mutation?: UseMutationOptions<{
        data: GenieAskOut;
    }, ApiError, {
        params: AskGenieParams;
        data: GenieAskIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>askGenie(vars.data, vars.params),
        ...options?.mutation
    });
}
export const genieConfig = async (options?: RequestInit): Promise<{
    data: GenieConfigOut;
}> =>{
    const res = await fetch("/api/genie/config", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const genieConfigKey = ()=>{
    return [
        "/api/genie/config"
    ] as const;
};
export function useGenieConfig<TData = {
    data: GenieConfigOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: GenieConfigOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: genieConfigKey(),
        queryFn: ()=>genieConfig(),
        ...options?.query
    });
}
export function useGenieConfigSuspense<TData = {
    data: GenieConfigOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: GenieConfigOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: genieConfigKey(),
        queryFn: ()=>genieConfig(),
        ...options?.query
    });
}
export interface MatchDetailParams {
    key: string;
}
export const matchDetail = async (params: MatchDetailParams, options?: RequestInit): Promise<{
    data: MatchDetailOut;
}> =>{
    const res = await fetch(`/api/matches/${params.key}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const matchDetailKey = (params?: MatchDetailParams)=>{
    return [
        "/api/matches/{key}",
        params
    ] as const;
};
export function useMatchDetail<TData = {
    data: MatchDetailOut;
}>(options: {
    params: MatchDetailParams;
    query?: Omit<UseQueryOptions<{
        data: MatchDetailOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: matchDetailKey(options.params),
        queryFn: ()=>matchDetail(options.params),
        ...options?.query
    });
}
export function useMatchDetailSuspense<TData = {
    data: MatchDetailOut;
}>(options: {
    params: MatchDetailParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: MatchDetailOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: matchDetailKey(options.params),
        queryFn: ()=>matchDetail(options.params),
        ...options?.query
    });
}
export interface PortfolioSummaryParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const portfolioSummary = async (params?: PortfolioSummaryParams, options?: RequestInit): Promise<{
    data: PortfolioOut;
}> =>{
    const res = await fetch("/api/portfolio/summary", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const portfolioSummaryKey = (params?: PortfolioSummaryParams)=>{
    return [
        "/api/portfolio/summary",
        params
    ] as const;
};
export function usePortfolioSummary<TData = {
    data: PortfolioOut;
}>(options?: {
    params?: PortfolioSummaryParams;
    query?: Omit<UseQueryOptions<{
        data: PortfolioOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: portfolioSummaryKey(options?.params),
        queryFn: ()=>portfolioSummary(options?.params),
        ...options?.query
    });
}
export function usePortfolioSummarySuspense<TData = {
    data: PortfolioOut;
}>(options?: {
    params?: PortfolioSummaryParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: PortfolioOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: portfolioSummaryKey(options?.params),
        queryFn: ()=>portfolioSummary(options?.params),
        ...options?.query
    });
}
export interface CreateRequestParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const createRequest = async (data: RequestIn, params?: CreateRequestParams, options?: RequestInit): Promise<{
    data: RequestOut;
}> =>{
    const res = await fetch("/api/requests", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useCreateRequest(options?: {
    mutation?: UseMutationOptions<{
        data: RequestOut;
    }, ApiError, {
        params: CreateRequestParams;
        data: RequestIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>createRequest(vars.data, vars.params),
        ...options?.mutation
    });
}
export interface CheckDuplicatesParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const checkDuplicates = async (data: DuplicateCheckIn, params?: CheckDuplicatesParams, options?: RequestInit): Promise<{
    data: DuplicateCheckOut;
}> =>{
    const res = await fetch("/api/requests/check-duplicates", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useCheckDuplicates(options?: {
    mutation?: UseMutationOptions<{
        data: DuplicateCheckOut;
    }, ApiError, {
        params: CheckDuplicatesParams;
        data: DuplicateCheckIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>checkDuplicates(vars.data, vars.params),
        ...options?.mutation
    });
}
export interface MyRequestsParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const myRequests = async (params?: MyRequestsParams, options?: RequestInit): Promise<{
    data: RequestOut[];
}> =>{
    const res = await fetch("/api/requests/mine", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const myRequestsKey = (params?: MyRequestsParams)=>{
    return [
        "/api/requests/mine",
        params
    ] as const;
};
export function useMyRequests<TData = {
    data: RequestOut[];
}>(options?: {
    params?: MyRequestsParams;
    query?: Omit<UseQueryOptions<{
        data: RequestOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: myRequestsKey(options?.params),
        queryFn: ()=>myRequests(options?.params),
        ...options?.query
    });
}
export function useMyRequestsSuspense<TData = {
    data: RequestOut[];
}>(options?: {
    params?: MyRequestsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: RequestOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: myRequestsKey(options?.params),
        queryFn: ()=>myRequests(options?.params),
        ...options?.query
    });
}
export interface ReviewQueueParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const reviewQueue = async (params?: ReviewQueueParams, options?: RequestInit): Promise<{
    data: ReviewItemOut[];
}> =>{
    const res = await fetch("/api/review/queue", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const reviewQueueKey = (params?: ReviewQueueParams)=>{
    return [
        "/api/review/queue",
        params
    ] as const;
};
export function useReviewQueue<TData = {
    data: ReviewItemOut[];
}>(options?: {
    params?: ReviewQueueParams;
    query?: Omit<UseQueryOptions<{
        data: ReviewItemOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: reviewQueueKey(options?.params),
        queryFn: ()=>reviewQueue(options?.params),
        ...options?.query
    });
}
export function useReviewQueueSuspense<TData = {
    data: ReviewItemOut[];
}>(options?: {
    params?: ReviewQueueParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: ReviewItemOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: reviewQueueKey(options?.params),
        queryFn: ()=>reviewQueue(options?.params),
        ...options?.query
    });
}
export interface ReviewRequestParams {
    request_id: string;
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const reviewRequest = async (params: ReviewRequestParams, data: ReviewIn, options?: RequestInit): Promise<{
    data: ReviewOut;
}> =>{
    const res = await fetch(`/api/review/${params.request_id}`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useReviewRequest(options?: {
    mutation?: UseMutationOptions<{
        data: ReviewOut;
    }, ApiError, {
        params: ReviewRequestParams;
        data: ReviewIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>reviewRequest(vars.params, vars.data),
        ...options?.mutation
    });
}
