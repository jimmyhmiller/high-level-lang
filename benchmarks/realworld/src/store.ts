// Application state in Redux Toolkit: the region the dashboard filters by, and notifications.
import { configureStore, createEntityAdapter, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { useDispatch, useSelector, type TypedUseSelectorHook } from 'react-redux';

export interface Notice {
  id: string;
  text: string;
  level: 'info' | 'warning';
}

const notices = createEntityAdapter<Notice>();

const ui = createSlice({
  name: 'ui',
  initialState: { region: 'All', compact: false, visits: [] as string[] },
  reducers: {
    regionChosen(state, action: PayloadAction<string>) {
      state.region = action.payload;
    },
    toggleCompact(state) {
      state.compact = !state.compact;
    },
    visited(state, action: PayloadAction<string>) {
      if (!state.visits.includes(action.payload)) state.visits.push(action.payload);
    },
  },
});

const notifications = createSlice({
  name: 'notifications',
  initialState: notices.getInitialState(),
  reducers: {
    added: notices.addOne,
    dismissed: notices.removeOne,
  },
});

export const { regionChosen, toggleCompact, visited } = ui.actions;
export const { added, dismissed } = notifications.actions;

export const store = configureStore({
  reducer: { ui: ui.reducer, notifications: notifications.reducer },
});

export type RootState = ReturnType<typeof store.getState>;
export const useAppDispatch: () => typeof store.dispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
export const noticeSelectors = notices.getSelectors((state: RootState) => state.notifications);
