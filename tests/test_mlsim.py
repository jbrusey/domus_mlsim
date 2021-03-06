import numpy as np
import pandas as pd
from pytest import approx
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import MinMaxScaler
from ux_transform import unroll_by_group

from domus_mlsim.mlsim import MLSim


def lr_model():
    return LinearRegression()


def test_mlsim():
    # learn a model first
    N = 100
    t = np.arange(0, N)
    k = 0.1
    a = 10
    c = 5
    yt = a * np.exp(-k * t) + c

    df = pd.DataFrame({"t": t, "y": yt})
    df = df.assign(u=0)
    pct40 = (N * 4) // 10

    xc = ["y"]
    uc = ["u"]

    sc_cols = xc + uc
    scaled_df = df[sc_cols]

    scaler = MinMaxScaler()

    scaled_df = pd.DataFrame(
        scaler.fit_transform(scaled_df), columns=sc_cols, index=df.index
    )

    scaled_df = scaled_df.assign(uc=[0] * pct40 + [1] * (N - pct40))
    scaled_df = scaled_df.dropna()
    xlag = 2
    X, y, groups = unroll_by_group(
        scaled_df, group_column="uc", x_columns=xc, u_columns=uc, xlag=xlag, ulag=2
    )

    X = X.to_numpy()
    y = y.to_numpy()

    xx, yy = X[groups == 0], y[groups == 0]

    # xt, yt = X[groups == 1], y[groups == 1]

    model = lr_model()
    _ = model.fit(xx, yy)

    initial_state = df.loc[0 : xlag - 1, xc].to_numpy()

    sim = MLSim(
        (scaler, model),
        initial_state=initial_state,
        xlag=2,
        ulag=2,
        xlen=1,
        ulen=1,
    )

    t, s1 = sim.step([0])

    assert approx(df.loc[xlag, xc].to_numpy()) == s1[0]
    assert t == 1

    t, s2 = sim.step([0])

    assert approx(df.loc[xlag + 1, xc].to_numpy()) == s2[0]
    assert t == 2


def test_two_lags():
    N = 10

    # set up a system such that y_t = f(y_t-1, x1, x2) and x_t is randomly chosen

    # e.g., y_t = - y_t-1 + x1 - 2 * x2

    x = np.random.random_sample(N)
    y = np.zeros((N))
    y[0] = 0
    for i in range(1, N):
        y[i] = -y[i - 1] + x[i] - 2 * x[i - 1]

    df = pd.DataFrame({"y": y, "x": x})
    print(df)
    scaler = MinMaxScaler()
    sc_cols = ["y", "x"]
    scaled_df = pd.DataFrame(scaler.fit_transform(df), columns=sc_cols, index=df.index)
    scaled_df = scaled_df.assign(uc=0)
    scaled_df = scaled_df.dropna()
    lag = 2
    print(scaled_df)
    X, y, groups = unroll_by_group(
        scaled_df,
        group_column="uc",
        x_columns=["y"],
        u_columns=["x"],
        xlag=lag,
        ulag=lag,
    )
    print(X)
    print(y)
    X, y = X.to_numpy(), y.to_numpy()

    model = lr_model()
    model.fit(X[groups == 0], y[groups == 0])

    initial_state = df.y.iloc[:lag].to_numpy().reshape(lag, -1)
    prior_actions = df.x.iloc[1:lag].to_numpy().reshape(lag - 1, -1)
    print(f"initial state {initial_state} and prior actions {prior_actions}")
    sim = MLSim(
        (scaler, model),
        initial_state,
        xlag=lag,
        ulag=lag,
        xlen=1,
        ulen=1,
        prior_actions=prior_actions,
    )

    u = df.x.to_numpy()[lag : lag + 1]
    t, xt = sim.step(u)
    print(f"sim.step({u}) -> {t}, {xt}")
    assert approx(xt[0]) == df.y.iloc[lag]

    for i in range(4):
        u = df.x.to_numpy()[lag + i + 1 : lag + i + 2]
        t, xt = sim.step(u)
        print(f"sim.step({u}) -> {t}, {xt}")
        assert approx(xt[0]) == df.y.iloc[lag + i + 1]


def test_one_lag():
    N = 10

    # set up a system such that y_t = f(y_t-1, x1, x2) and x_t is randomly chosen

    # e.g., y_t = - 2 * y_t-1 + 3 * x1

    x = np.random.random_sample(N)
    y = np.zeros((N))
    y[0] = 0
    for i in range(1, N):
        y[i] = -2 * y[i - 1] + 3 * x[i]

    df = pd.DataFrame({"y": y, "x": x})
    scaler = MinMaxScaler()
    sc_cols = ["y", "x"]
    scaled_df = pd.DataFrame(scaler.fit_transform(df), columns=sc_cols, index=df.index)
    scaled_df = scaled_df.assign(uc=0)
    scaled_df = scaled_df.dropna()
    lag = 1
    X, y, groups = unroll_by_group(
        scaled_df,
        group_column="uc",
        x_columns=["y"],
        u_columns=["x"],
        xlag=lag,
        ulag=lag,
    )
    X, y = X.to_numpy(), y.to_numpy()

    model = lr_model()
    model.fit(X[groups == 0], y[groups == 0])

    initial_state = np.vstack(df.y.iloc[:lag])
    sim = MLSim((scaler, model), initial_state, xlag=lag, ulag=lag, xlen=1, ulen=1)

    t, xt = sim.step(df.x.iloc[lag])
    assert xt.shape == (1,)
    assert approx(xt[0]) == df.y.iloc[lag]

    for i in range(4):
        u = df.x.to_numpy()[lag + i + 1 : lag + i + 2]
        t, xt = sim.step(u)
        print(f"sim.step({u}) -> {t}, {xt}")
        assert approx(xt[0]) == df.y.iloc[lag + i + 1]


def test_clip():
    N = 10
    x = np.random.random_sample(N)
    y = np.zeros((N))
    y[0] = 0
    for i in range(1, N):
        y[i] = -2 * y[i - 1] + 3 * x[i]

    df = pd.DataFrame({"y": y, "x": x})
    scaler = MinMaxScaler()
    sc_cols = ["y", "x"]
    scaled_df = pd.DataFrame(scaler.fit_transform(df), columns=sc_cols, index=df.index)
    scaled_df = scaled_df.assign(uc=0)
    scaled_df = scaled_df.dropna()
    lag = 1
    X, y, groups = unroll_by_group(
        scaled_df,
        group_column="uc",
        x_columns=["y"],
        u_columns=["x"],
        xlag=lag,
        ulag=lag,
    )
    X, y = X.to_numpy(), y.to_numpy()

    model = lr_model()
    model.fit(X[groups == 0], y[groups == 0])

    initial_state = np.array([[100]])
    sim = MLSim(
        (scaler, model),
        initial_state,
        xlag=lag,
        ulag=lag,
        xlen=1,
        ulen=1,
        ut_min=np.array([0]),
        ut_max=np.array([1]),
    )

    # try a value that is larger than ut max
    t, xt = sim.step(33)
    # it should squash to 1
    assert approx(xt[0]) == -2 * 100 + 3 * 1

    old_x = xt[0]
    # try a value smaller than ut min
    t, xt = sim.step(-9)
    assert approx(xt[0]) == -2 * old_x + 3 * 0

    old_x = xt[0]
    # try a value in between
    t, xt = sim.step(0.7)
    assert approx(xt[0]) == -2 * old_x + 3 * 0.7
